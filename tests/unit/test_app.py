import pytest
import json
from unittest.mock import MagicMock
from src.app import RabbitMQClient, HTTPException
import pika

# Fixture de preparación

@pytest.fixture
def mocked_client(mocker):
    """
    Fixture que crea un RabbitMQClient con todas las llamadas de red
    simuladas (mockeadas) para pruebas unitarias.
    """
    mock_conn = mocker.MagicMock()
    mock_chan = mocker.MagicMock()

    mock_queue_result = mocker.MagicMock()
    mock_queue_result.method.queue = "fake_callback_queue_123"
    mock_chan.queue_declare.return_value = mock_queue_result

    mock_conn.channel.return_value = mock_chan

    mocker.patch("pika.BlockingConnection", return_value=mock_conn)
    mocker.patch("pika.BasicProperties", side_effect=lambda **kwargs: kwargs)

    client = RabbitMQClient()
    client.connect()

    client.mock_conn = mock_conn
    client.mock_chan = mock_chan

    yield client


@pytest.mark.parametrize(
    "scenario,response_map,expected_calls,expected_result,expected_exception",
    [
        # Escenario 1: Éxito inmediato
        (
            "success_first_try",
            {0: {"status": "success", "counter": 5}},
            1,
            {"status": "success", "counter": 5},
            None,
        ),
        # Escenario 2: Error en los dos primeros intentos, luego éxito
        (
            "error_then_success",
            {
                0: {"status": "error", "message": "temporary failure"},
                1: {"status": "error", "message": "still failing"},
                2: {"status": "success", "counter": 8},
            },
            3,
            {"status": "success", "counter": 8},
            None,
        ),
        # 🔴 Escenario 3: Siempre error lógico del worker → reintentos fallidos
        (
            "persistent_worker_error",
            {
                0: {"status": "error", "message": "Redis down"},
                1: {"status": "error", "message": "Redis down"},
                2: {"status": "error", "message": "Redis down"},
                3: {"status": "error", "message": "Redis down"},
                4: {"status": "error", "message": "Redis down"},
            },
            5,
            None,
            HTTPException,  # Esperamos HTTP 502 del cliente
        ),
        # ⚫ Escenario 4: Timeout (sin respuesta)
        (
            "no_response_timeout",
            {0: None, 1: None, 2: None, 3: None, 4: None},
            5,
            None,
            HTTPException,  # Esperamos HTTP 504
        ),
    ],
)
def test_call_retry_scenarios(
    mocked_client,
    mocker,
    scenario,
    response_map,
    expected_calls,
    expected_result,
    expected_exception,
):
    print(f"--- Escenario: {scenario} ---")

    test_message = {"action": "TEST"}
    mocker.patch("time.sleep")  # Evita esperas reales

    attempt_counter = [0]

    def side_effect_func(time_limit):
        """Simula la respuesta del broker en cada intento."""
        current_attempt = attempt_counter[0]
        response_data = response_map.get(current_attempt)

        if response_data is not None:
            mocked_client.response = json.dumps(response_data).encode("utf-8")
        else:
            mocked_client.response = None  # Simula timeout

        attempt_counter[0] += 1

    mocked_client.mock_conn.process_data_events.side_effect = side_effect_func

    if expected_exception:
        with pytest.raises(HTTPException) as e:
            mocked_client.call(test_message)

        if scenario == "persistent_worker_error":
            assert e.value.status_code == 500
        elif scenario == "no_response_timeout":
            assert e.value.status_code == 500
        else:
            pytest.fail("Unexpected exception scenario")

    else:
        result = mocked_client.call(test_message)
        assert result == expected_result

    assert mocked_client.mock_chan.basic_publish.call_count == expected_calls