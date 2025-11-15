import redis
from src.ports.repository import ICounterRepository
import os

class RedisCounterRepository(ICounterRepository):
    """
    Implementación concreta (Adapter) que usa Redis
    para manejar el contador.
    """

    def __init__(self):
        
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379)) 

        # Conecta con la BD
        self.client = redis.Redis(
            host=redis_host, port=redis_port, db=0, decode_responses=True
        )

    def incrementCounter(self, n: int) -> None:
        print(f"ADAPTER: Incrementando contador en {n}")
        self.client.incrby("counter", n)

    def getCounter(self) -> int:
        print("ADAPTER: Obteniendo contador")
        value = self.client.get("counter")
        # Caso límite: si la llave no existe, Redis devuelve None
        return int(value) if value else 0
