import json
from src.worker import Worker
from src.ports.repository import ICounterRepository
from unittest.mock import MagicMock, create_autospec, ANY


def test_worker_increment_action(mocker):
    """
    Prueba que el worker llama a repository.incrementCounter
    cuando recibe una acción de INCREMENT_COUNTER.
    """
    # 1. Arrange
    mock_repo = create_autospec(ICounterRepository)

    mock_repo.getCounter.return_value = 1

    # Mockeamos Pika
    mocker.patch("pika.BlockingConnection", return_value=mocker.MagicMock())

    # Instanciamos el Worker con el adapter mockeado
    worker = Worker(repository=mock_repo)

    # Simulamos los argumentos del callback
    mock_channel = mocker.MagicMock()
    mock_method = mocker.MagicMock(delivery_tag=123)

    # Debe ser un JSON válido que el worker espera
    test_body = json.dumps(
        {"action": "INCREMENT_COUNTER", "increment": 1, "delay": 0}
    ).encode("utf-8")

    # Debe ser un objeto con 'reply_to' y 'correlation_id'
    mock_properties = mocker.MagicMock()
    mock_properties.reply_to = "fake_reply_queue"
    mock_properties.correlation_id = "fake_corr_id"

    # 2. Act
    worker.on_message_received(mock_channel, mock_method, mock_properties, test_body)

    # 3. Assert
    # Verificamos que el worker usó el adapter
    mock_repo.incrementCounter.assert_called_once_with(1)

    mock_repo.getCounter.assert_called_once()

    mock_channel.basic_publish.assert_called_once_with(
        exchange="", routing_key="fake_reply_queue", properties=ANY, body=ANY
    )

    # Verificamos que el worker confirmó el mensaje al broker
    mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)
