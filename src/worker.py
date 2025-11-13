import pika
from .ports.repository import ICounterRepository
import time

class Worker:
    def __init__(self, repository: ICounterRepository):
        # El Worker recibe el Adapter por Inyección de Dependencias
        self.repository = repository

        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', port=5671))
        self.channel = connection.channel()
        self.channel.queue_declare(queue='tasks_queue')

    def on_message_received(self, ch, method, properties, body):
        """Callback que se ejecuta cuando llega un mensaje."""
        print(f"WORKER: Mensaje recibido: {body}")
        
        # Usamos el Adapter (sin saber que es Redis)
        self.repository.incrementCounter(1)
        
        print("WORKER: Tarea completada.")
        ch.basic_ack(delivery_tag=method.delivery_tag)

        print("WORKER: Esperando mensajes...")

    def start_consuming(self):
        print("WORKER: Esperando mensajes...")
        self.channel.basic_consume(
            queue='tasks_queue',
            on_message_callback=self.on_message_received
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
        