import pytest
from src.adapters.redis_repository import RedisCounterRepository

# Usamos 'mocker' de la librería pytest-mock
def test_increment_counter_calls_incrby(mocker):
    """
    Prueba que el método 'incrementCounter' llama al cliente
    de redis con los argumentos correctos.
    """
    # Creamos un mock del cliente de redis
    mock_redis_client = mocker.MagicMock()
    
    # "Engañamos" a la clase para que use nuestro mock en lugar del real
    mocker.patch('redis.Redis', return_value=mock_redis_client)

    # Creamos la instancia y llamamos al método
    repo = RedisCounterRepository()
    repo.incrementCounter(5)

    # Verificamos que se llamó al mock
    mock_redis_client.incrby.assert_called_once_with("counter", 5)

@pytest.mark.parametrize("redis_value, expected_return", [
    ("10", 10),  # Caso normal
    (None, 0),   # Caso límite (key no existe)
    ("5", 5),
])
def test_get_counter_handles_values(mocker, redis_value, expected_return):
    """
    Prueba que 'getCounter' maneja diferentes valores de Redis.
    """
    mock_redis_client = mocker.MagicMock()
    mock_redis_client.get.return_value = redis_value # Simulamos la rpta de Redis
    mocker.patch('redis.Redis', return_value=mock_redis_client)

    repo = RedisCounterRepository()
    result = repo.getCounter()

    mock_redis_client.get.assert_called_once_with("counter")
    assert result == expected_return