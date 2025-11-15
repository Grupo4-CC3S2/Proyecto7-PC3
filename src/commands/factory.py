from .increment_command import IncrementCounterCommand
from .get_counter_command import GetCounterCommand

class CommandFactory:
    @staticmethod
    def create(action, data, repository):
        if action == "INCREMENT_COUNTER":
            return IncrementCounterCommand(
                repository=repository,
                increment=data.get("increment", 1),
                delay=data.get("delay", 1)
            )
        
        if action == "GET_COUNTER":
            return GetCounterCommand(repository)

        raise ValueError(f"Acción desconocida: {action}")
