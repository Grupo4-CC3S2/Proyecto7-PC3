import pika
import json
from .ports.repository import ICounterRepository
import time


class Worker:
    def __init__(self, repository: ICounterRepository):
        # El Worker recibe el Adapter por Inyección de Dependencias
        self.repository = repository

        connection = pika.BlockingConnection(
            pika.ConnectionParameters("localhost", port=5671)
        )
        self.channel = connection.channel()
        self.channel.queue_declare(queue="tasks_queue", durable=True)

    def on_message_received(self, ch, method, properties, body):
        """Callback que se ejecuta cuando llega un mensaje."""
        print(f"WORKER: Mensaje recibido: {body}")

        data = json.loads(body)
        action = data.get("action")
        increment = data.get("increment", 1)
        delay = data.get("delay", 1)  # segundos entre pasos

        if action == "INCREMENT_COUNTER":
            print(f"WORKER: Incrementando contador en {increment} con delay {delay}s")

            # Simula incremento por pasos (p. ej., 1 en 1)
            for i in range(increment):
                self.repository.incrementCounter(1)
                time.sleep(delay)
                print(f"WORKER: Paso {i+1}/{increment} completado")

            result = {
                "status": "success",
                "message": f"Incremento completado ({increment})",
                "counter": self.repository.getCounter(),
            }

        elif action == "GET_COUNTER":
            current = self.repository.getCounter()
            result = {"status": "success", "counter": current}

        else:
            result = {"status": "error", "error": f"Acción desconocida: {action}"}

        # Enviar respuesta si el cliente lo pidió
        if properties.reply_to:
            ch.basic_publish(
                exchange="",
                routing_key=properties.reply_to,
                properties=pika.BasicProperties(
                    correlation_id=properties.correlation_id,
                    content_type="application/json",
                ),
                body=json.dumps(result),
            )
            print(f"WORKER: Respuesta enviada a {properties.reply_to}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    def start_consuming(self):
        print("WORKER: Esperando mensajes...")
        self.channel.basic_consume(
            queue="tasks_queue", on_message_callback=self.on_message_received
        )
        self.channel.start_consuming()


if __name__ == "__main__":
    from .adapters.redis_repository import RedisCounterRepository

    print("WORKER: Iniciando...")

    try:
        repository = RedisCounterRepository()

        worker = Worker(repository=repository)

        worker.start_consuming()

    except Exception as e:
        print(f"WORKER: Error de conexión")
        print(f"Error: {e}")
