import time
from .base import Command
from .chaos import ChaosMixin

class IncrementCounterCommand(Command, ChaosMixin):
    def __init__(self, repository, increment, delay):
        self.repository = repository
        self.increment = increment
        self.delay = delay
        self.completed_steps = 0  # pasos exitosos

    def execute(self):

        try:
            # ejecución paso a paso
            for i in range(self.increment):
                # caos por paso (controlado)
                chaos = self.chaos_check()
                if chaos:
                    raise Exception("Chaos during step execution")

                # acción real
                self.repository.incrementCounter(1)
                self.completed_steps += 1

                time.sleep(self.delay)

            # si todo salió bien
            return {
                "status": "success",
                "message": f"Incremento completado ({self.increment})",
                "counter": self.repository.getCounter()
            }

        except Exception as e:
            self.compensate()
            return {
                "status": "error",
                "detail": f"Proceso interrumpido y compensado: {str(e)}",
                "steps_completed": self.completed_steps
            }

    def compensate(self):
        """Deshace los incrementos exitosos previos."""
        for _ in range(self.completed_steps):
            self.repository.incrementCounter(-1)
