from .base import Command
from .chaos import ChaosMixin

class GetCounterCommand(Command, ChaosMixin):
    def __init__(self, repository):
        self.repository = repository

    def execute(self):
        chaos = self.chaos_check()
        if chaos:
            return chaos

        return {
            "status": "success",
            "counter": self.repository.getCounter()
        }
