from src.worker import Worker
from src.ports.repository import ICounterRepository
from unittest.mock import MagicMock, create_autospec

def test_worker_calls_repository_on_message(mocker):
    """
    Prueba que el worker llama a repository.incrementCounter
    cuando recibe un mensaje.
    """
    # 1. Arrange
    # Creamos un mock del Adapter
    # Usamos create_autospec para que el mock siga la firma
    mock_repo = create_autospec(ICounterRepository)
    
    # Mockeamos Pika para no conectarnos a RabbitMQ
    mocker.patch('pika.BlockingConnection', return_value=mocker.MagicMock())
    
    # Instanciamos el Worker con el adapter mockeado
    worker = Worker(repository=mock_repo)
    
    # Simulamos los argumentos que Pika le pasaría al callback
    mock_channel = mocker.MagicMock()
    mock_method = mocker.MagicMock(delivery_tag=123)

    # 2. Act
    # Llamamos al callback directamente
    worker.on_message_received(mock_channel, mock_method, None, b"increment")

    # 3. Assert
    # Verificamos que el worker usó el adapter
    mock_repo.incrementCounter.assert_called_once_with(1)
    
    # Verificamos que el worker confirmó el mensaje al broker
    mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)