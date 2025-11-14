"""
FastAPI service for counter operations with RabbitMQ
Endpoints:
  GET  /api/counter/     - Get current counter value
  POST /api/counter/{n}  - Increment counter by n (default 1)
"""

from fastapi import Query
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pika
import json
import uuid
from typing import Optional
import logging
import os
from .resilience.retry import retry_with_backoff

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de RabbitMQ desde variables de entorno
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 6))
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5671))
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "tasks_queue")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
API_VERSION = os.getenv("API_VERSION", "1.0.0")

app = FastAPI(title="Counter API", version=API_VERSION)


class CounterResponse(BaseModel):
    """Response model for counter operations"""

    status: str
    counter: int
    message: Optional[str] = None


class RabbitMQClient:
    """Cliente RabbitMQ con patrón Request-Reply"""

    def __init__(self):
        self.host = RABBITMQ_HOST
        self.port = RABBITMQ_PORT
        self.queue = RABBITMQ_QUEUE
        self.user = RABBITMQ_USER
        self.password = RABBITMQ_PASSWORD
        self.connection = None
        self.channel = None
        self.callback_queue = None
        self.response = None
        self.corr_id = None

    def connect(self):
        """Establece conexión con RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.user, self.password)
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.host, port=self.port, credentials=credentials
                )
            )
            self.channel = self.connection.channel()

            # Declarar la cola principal de tareas (compartida)
            self.channel.queue_declare(queue=self.queue, durable=True)

            # Crear una cola temporal (anónima) solo para respuestas
            result = self.channel.queue_declare(queue="", exclusive=True)
            self.callback_queue = result.method.queue

            # Consumir respuestas
            self.channel.basic_consume(
                queue=self.callback_queue,
                on_message_callback=self.on_response,
                auto_ack=True,
            )

            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise HTTPException(status_code=503, detail="Message broker unavailable")

    def on_response(self, ch, method, props, body):
        """Callback cuando llega respuesta del worker"""
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, message):
        """
        Envía un mensaje a RabbitMQ y espera una respuesta, con reintentos
        """

        def send_message():
            if not self.connection or self.connection.is_closed:
                self.connect()

            self.corr_id = str(uuid.uuid4())
            self.response = None

            self.channel.basic_publish(
                exchange="",
                routing_key=self.queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    reply_to=self.callback_queue,
                    correlation_id=self.corr_id,
                    content_type="application/json",
                ),
            )

            # Espera hasta 11s a que llegue la respuesta
            self.connection.process_data_events(time_limit=11)

            if not self.response:
                raise TimeoutError("No response received")

            # Decodificar JSON
            response = json.loads(self.response)

            # Si el worker responde con error explícito, forzar reintento
            if response.get("status") == "error":
                raise RuntimeError(response.get("message", "Worker returned error"))

            return response

        try:
            # Reintenta solo si send_message lanza excepción (timeout o error lógico)
            result = retry_with_backoff(send_message, max_retries=MAX_RETRIES, base_delay=1)

            logger.info(f"Worker response: {result}")
            return result

        except TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Worker timeout - no response received"
            )

        except RuntimeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Worker failed after retries {MAX_RETRIES}: {str(e)}"
            )

        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail="Invalid JSON response from worker"
            )

        except Exception as e:
            logger.error(f"Unexpected error in call(): {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal error: {str(e)}"
            )


    def close(self):
        """Cierra conexión"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Connection closed")


# Cliente global (reutilizable)
rabbitmq_client = RabbitMQClient()


@app.on_event("startup")
async def startup_event():
    """Inicializar conexión al arrancar"""
    try:
        rabbitmq_client.connect()
        logger.info("API started successfully")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # No detener la app, intentará reconectar en cada request


@app.on_event("shutdown")
async def shutdown_event():
    """Cerrar conexión al apagar"""
    rabbitmq_client.close()
    logger.info("API shutdown complete")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"service": "Counter API", "status": "running", "version": "1.0.0"}


@app.get("/api/counter/", response_model=CounterResponse)
async def get_counter():
    """
    Get current counter value

    Sends GET_COUNTER message to RabbitMQ and waits for response
    """
    try:
        message = {"action": "GET_COUNTER"}

        result = rabbitmq_client.call(message)

        if result.get("status") == "success":
            return CounterResponse(
                status="ok",
                counter=result.get("counter", 0),
                message="Counter retrieved successfully",
            )
        else:
            raise HTTPException(
                status_code=500, detail=result.get("error", "Unknown error")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_counter: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/api/counter/", response_model=CounterResponse)
@app.post("/api/counter/{n}", response_model=CounterResponse)
async def increment_counter(
    n: int = 1,
    delay: float = Query(0.1, ge=0, le=10, description="Delay entre pasos en segundos"),
):
    """
    Increment counter by n

    Args:
        n: Amount to increment (default: 1)
        delay: Delay entre cada incremento (segundos)

    Sends INCREMENT_COUNTER message to RabbitMQ and waits for response
    """

    if n < 0:
        raise HTTPException(status_code=400, detail="Increment value must be positive")

    if n > 1000:
        raise HTTPException(
            status_code=400, detail="Increment value too large (max: 1000)"
        )

    try:
        message = {"action": "INCREMENT_COUNTER", "increment": n, "delay": delay}

        result = rabbitmq_client.call(message)

        if result.get("status") == "success":
            return CounterResponse(
                status="ok",
                counter=result.get("counter", 0),
                message=f"Counter incremented by {n} with delay={delay}s",
            )
        else:
            raise HTTPException(
                status_code=500, detail=result.get("error", "Unknown error")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in increment_counter: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
