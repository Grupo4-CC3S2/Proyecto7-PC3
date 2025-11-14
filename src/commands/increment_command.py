import time
from .base import Command
from .chaos import ChaosMixin


class IncrementCounterCommand(Command, ChaosMixin):
    def __init__(self, repository, increment, delay):
        self.repository = repository
        self.increment = increment
        self.delay = delay

    def execute(self):
        # chequeo de caos antes de lógica real
        chaos = self.chaos_check()
        if chaos:
            return chaos

        for i in range(self.increment):
            self.repository.incrementCounter(1)
            time.sleep(self.delay)

        return {
            "status": "success",
            "message": f"Incremento completado ({self.increment})",
            "counter": self.repository.getCounter()
        }