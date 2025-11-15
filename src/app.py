"""
FastAPI service for counter operations with RabbitMQ + DLQ
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
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 4))
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5671))
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "tasks_queue")
RABBITMQ_DLQ = os.getenv("RABBITMQ_DLQ", "tasks_queue_dlq")
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
    """Cliente RabbitMQ con patrón Request-Reply y DLQ"""

    def __init__(self):
        self.host = RABBITMQ_HOST
        self.port = RABBITMQ_PORT
        self.queue = RABBITMQ_QUEUE
        self.dlq = RABBITMQ_DLQ
        self.user = RABBITMQ_USER
        self.password = RABBITMQ_PASSWORD
        self.connection = None
        self.channel = None
        self.callback_queue = None
        self.response = None
        self.corr_id = None

    def connect(self):
        """Establece conexión con RabbitMQ y declara colas con DLQ"""
        try:
            credentials = pika.PlainCredentials(self.user, self.password)
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.host, port=self.port, credentials=credentials
                )
            )
            self.channel = self.connection.channel()

            # Declarar la Dead Letter Queue (sin DLX para evitar loops)
            self.channel.queue_declare(
                queue=self.dlq,
                durable=True,
                arguments={
                    'x-queue-type': 'quorum'
                }
            )
            logger.info(f"Dead Letter Queue '{self.dlq}' declared")

            # Declarar la cola principal con DLX apuntando a DLQ
            self.channel.queue_declare(
                queue=self.queue,
                durable=True,
                arguments={
                    'x-dead-letter-exchange': '',  # Default exchange
                    'x-dead-letter-routing-key': self.dlq,
                    'x-queue-type': 'quorum'
                }
            )
            logger.info(f"Main queue '{self.queue}' declared with DLQ support")

            # Crear cola temporal para respuestas
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

    def send_to_dlq(self, message, reason, correlation_id):
        """
        Envía un mensaje directamente a la DLQ con metadata de error
        """
        try:
            if not self.connection or self.connection.is_closed:
                self.connect()

            # Agregar metadata de error
            dlq_message = {
                'original_message': message,
                'error_reason': reason,
                'correlation_id': correlation_id,
                'failed_at': str(uuid.uuid1().time),
                'max_retries_reached': True
            }

            self.channel.basic_publish(
                exchange='',
                routing_key=self.dlq,
                body=json.dumps(dlq_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent
                    content_type='application/json',
                    headers={
                        'x-original-queue': self.queue,
                        'x-error-reason': reason,
                        'x-correlation-id': correlation_id
                    }
                )
            )
            logger.warning(
                f"[DLQ] Message sent to DLQ: {correlation_id} | Reason: {reason}"
            )

        except Exception as e:
            logger.error(f"Failed to send message to DLQ: {e}")

    def call(self, message):
        """
        Envía un mensaje a RabbitMQ y espera una respuesta
        Si falla después de todos los reintentos, lo envía a DLQ
        """

        def send_message():
            if not self.connection or self.connection.is_closed:
                self.connect()

            self.corr_id = str(uuid.uuid4())
            self.response = None

            # Agregar contador de reintentos al mensaje
            if 'retry_count' not in message:
                message['retry_count'] = 0
            
            message['retry_count'] += 1

            self.channel.basic_publish(
                exchange="",
                routing_key=self.queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    reply_to=self.callback_queue,
                    correlation_id=self.corr_id,
                    content_type="application/json",
                    delivery_mode=2,  # Persistent
                ),
            )

            # Espera hasta 11s a que llegue la respuesta
            max_timeout = 2**(MAX_RETRIES-1) + 1 ## tiempo máximo de espera segun MAX_RETRIES
            self.connection.process_data_events(time_limit= max_timeout)

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

        except (TimeoutError, RuntimeError) as e:
            error_reason = str(e)
            
            # Enviar a DLQ después de agotar reintentos
            self.send_to_dlq(
                message=message,
                reason=error_reason,
                correlation_id=self.corr_id
            )
            
            # Determinar tipo de error
            if isinstance(e, TimeoutError):
                raise HTTPException(
                    status_code=504,
                    detail=f"Worker timeout after {MAX_RETRIES} retries. Message sent to DLQ."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Worker failed after {MAX_RETRIES} retries. Message sent to DLQ: {error_reason}"
                )

        except json.JSONDecodeError:
            # También enviar a DLQ si la respuesta es inválida
            self.send_to_dlq(
                message=message,
                reason="Invalid JSON response from worker",
                correlation_id=self.corr_id
            )
            
            raise HTTPException(
                status_code=500,
                detail="Invalid JSON response from worker. Message sent to DLQ."
            )

        except Exception as e:
            logger.error(f"Unexpected error in call(): {e}")
            
            # Enviar a DLQ por errores inesperados
            self.send_to_dlq(
                message=message,
                reason=f"Unexpected error: {str(e)}",
                correlation_id=self.corr_id
            )
            
            raise HTTPException(
                status_code=500,
                detail=f"Internal error. Message sent to DLQ: {str(e)}"
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


@app.get("/api/dlq/stats")
async def get_dlq_stats():
    """
    Get Dead Letter Queue statistics
    
    Returns number of messages in DLQ
    """
    try:
        if not rabbitmq_client.connection or rabbitmq_client.connection.is_closed:
            rabbitmq_client.connect()
        
        # Obtener info de la DLQ sin modificarla
        queue_info = rabbitmq_client.channel.queue_declare(
            queue=rabbitmq_client.dlq,
            durable=True,
            passive=True  # Solo obtener info, no crear
        )
        
        message_count = queue_info.method.message_count
        
        return {
            "dlq_name": rabbitmq_client.dlq,
            "message_count": message_count,
            "status": "warning" if message_count > 0 else "ok",
            "timestamp": str(uuid.uuid1().time)
        }
        
    except Exception as e:
        logger.error(f"Error getting DLQ stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get DLQ stats: {str(e)}"
        )


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