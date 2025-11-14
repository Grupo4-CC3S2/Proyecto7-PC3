import pika
import json
from .commands.factory import CommandFactory

class Worker:
    def __init__(self, repository):
        self.repository = repository

        connection = pika.BlockingConnection(
            pika.ConnectionParameters("localhost", port=5671)
        )
        self.channel = connection.channel()
        self.channel.queue_declare(queue="tasks_queue", durable=True)

    def on_message_received(self, ch, method, properties, body):
        print(f"WORKER: mensaje recibido: {body}")

        data = json.loads(body)
        action = data.get("action")

        try:
            # Crear el command
            command = CommandFactory.create(action, data, self.repository)
            # Ejecutar
            result = command.execute()

        except Exception as e:
            print(f"WORKER: Error procesando el mensaje {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print(f"WORKER: resultado: {result}")
        
        # Responder si aplica
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
