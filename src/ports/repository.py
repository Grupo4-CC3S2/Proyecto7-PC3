from abc import ABC, abstractmethod


class ICounterRepository(ABC):
    """
    Define la interfaz (Puerto) para el repositorio de contadores.
    El Worker dependerá de esta abstracción, no de Redis.
    """

    @abstractmethod
    def incrementCounter(self, n: int) -> None:
        """Incrementa el contador en 'n'."""
        pass

    @abstractmethod
    def getCounter(self) -> int:
        """Obtiene el valor actual del contador."""
        pass
