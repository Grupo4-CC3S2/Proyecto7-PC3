import pika
import json
from .commands.factory import CommandFactory
import time

class Worker:
    def __init__(self, repository,queue="tasks_queue",dlq="tasks_queue_dlq"):
        self.repository = repository
        self.queue = queue
        self.dlq = dlq
        connection = pika.BlockingConnection(
            pika.ConnectionParameters("localhost", port=5671)
        )
        self.channel = connection.channel()
        self.channel.queue_declare(
            queue=self.dlq,
            durable=True,
            arguments={
                'x-queue-type': 'quorum'
            }
        )
        print(f"WORKER: Dead Letter Queue '{self.dlq}' declared")

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
    while True:
        try:
            repository = RedisCounterRepository()

            worker = Worker(repository=repository)

            worker.start_consuming()

        except Exception as e:
            print(f"Error: {e}")
            print(f"WORKER: Error de conexión")
            print("WORKER: Reintentando en 5 segundos...")
            time.sleep(5)
            
