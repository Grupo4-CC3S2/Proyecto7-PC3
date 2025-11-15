import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from src.app import app

@pytest.fixture(autouse=True)
def mock_rabbitmq_client(mocker):
    """
    Mockea el cliente global rabbitmq_client ANTES de que la app
    intente conectarse en su evento de 'startup'.
    """
    mock_client = MagicMock()
    
    # Simulamos los métodos que usa la app
    mock_client.connect.return_value = None
    mock_client.close.return_value = None
    mock_client.call.return_value = None 

    mocker.patch('src.app.rabbitmq_client', mock_client)
    
    return mock_client

@pytest.fixture()
def client():
    """
    Proporciona una instancia de TestClient para hacer peticiones HTTP
    a nuestra app de FastAPI.
    """
    with TestClient(app) as test_client:
        yield test_client

# Tests de Endpoints
def test_get_counter_success(client, mock_rabbitmq_client):
    """
    Prueba el endpoint GET /api/counter/
    """
    # 1. Arrange: Simula la respuesta del worker
    mock_rabbitmq_client.call.return_value = {
        "status": "success",
        "counter": 42
    }

    # 2. Act: Llama al endpoint de la API
    response = client.get("/api/counter/")

    # 3. Assert
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["counter"] == 42
    # Verifica que se llamó al backend con el mensaje correcto
    mock_rabbitmq_client.call.assert_called_with({"action": "GET_COUNTER"})

def test_post_counter_success(client, mock_rabbitmq_client):
    """
    Prueba el endpoint POST /api/counter/
    """
    # 1. Arrange
    mock_rabbitmq_client.call.return_value = {
        "status": "success",
        "counter": 3
    }

    # 2. Act
    response = client.post("/api/counter/3?delay=0.1")

    # 3. Assert
    assert response.status_code == 200
    assert response.json()["counter"] == 3
    # Verifica que se llamó al backend con el mensaje correcto
    mock_rabbitmq_client.call.assert_called_with({
        "action": "INCREMENT_COUNTER",
        "increment": 3,
        "delay": 0.1
    })

def test_post_counter_invalid_n_fails(client, mock_rabbitmq_client):
    """
    Prueba la validación de entrada (n < 0)
    """
    # 1. Act: Llama al endpoint con un valor negativo
    response = client.post("/api/counter/-1")
    
    # 2. Assert: Debe fallar con un 400 ANTES de llamar a RabbitMQ
    assert response.status_code == 400
    assert "must be positive" in response.json()["detail"]
    # Verifica que NUNCA se llamó al backend
    mock_rabbitmq_client.call.assert_not_called()

def test_root_health_check(client):
    """
    Prueba el endpoint / (health check).
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Counter API"

def test_post_counter_too_large_fails(client, mock_rabbitmq_client):
    """
    Prueba la validación de n > 1000.
    """
    response = client.post("/api/counter/1001")
    assert response.status_code == 400
    assert "too large" in response.json()["detail"]
    mock_rabbitmq_client.call.assert_not_called()

def test_get_counter_worker_error(client, mock_rabbitmq_client):
    """
    Prueba qué pasa si el worker responde con {"status": "error"} en un GET.
    """
    # 1. Arrange: Simula una respuesta de error del worker
    mock_rabbitmq_client.call.return_value = {
        "status": "error",
        "error": "Simulated Worker Error"
    }

    # 2. Act
    response = client.get("/api/counter/")

    # 3. Assert: La API debe convertirlo en un HTTP 500
    assert response.status_code == 500
    assert "Simulated Worker Error" in response.json()["detail"]

def test_increment_counter_worker_error(client, mock_rabbitmq_client):
    """
    Prueba qué pasa si el worker responde con {"status": "error"} en un POST.
    """
    # 1. Arrange
    mock_rabbitmq_client.call.return_value = {
        "status": "error",
        "error": "Simulated Worker Error"
    }

    # 2. Act
    response = client.post("/api/counter/5")

    # 3. Assert
    assert response.status_code == 500
    assert "Simulated Worker Error" in response.json()["detail"]

def test_get_counter_raises_unexpected_exception(client, mock_rabbitmq_client):
    """
    Prueba el 'except Exception as e' en get_counter()
    """
    # 1. Arrange
    mock_rabbitmq_client.call.side_effect = Exception("Error de red simulado")

    # 2. Act
    response = client.get("/api/counter/")

    # 3. Assert
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
    assert "Error de red simulado" in response.json()["detail"]


def test_increment_counter_raises_unexpected_exception(client, mock_rabbitmq_client):
    """
    Prueba el 'except Exception as e' en increment_counter()
    """
    # 1. Arrange
    mock_rabbitmq_client.call.side_effect = Exception("Error de red simulado")

    # 2. Act
    response = client.post("/api/counter/1")

    # 3. Assert
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
    assert "Error de red simulado" in response.json()["detail"]