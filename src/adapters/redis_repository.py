import redis
from src.ports.repository import ICounterRepository

class RedisCounterRepository(ICounterRepository):
    """
    Implementación concreta (Adapter) que usa Redis
    para manejar el contador.
    """
    def __init__(self, redis_host: str = 'localhost'):
        # Conecta con la BD del Paso 1
        self.client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)

    def incrementCounter(self, n: int) -> None:
        print(f"ADAPTER: Incrementando contador en {n}")
        self.client.incrby("counter", n)

    def getCounter(self) -> int:
        print("ADAPTER: Obteniendo contador")
        value = self.client.get("counter")
        # Caso límite: si la llave no existe, Redis devuelve None
        return int(value) if value else 0