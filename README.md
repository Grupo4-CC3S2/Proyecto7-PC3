# Proyecto 7: Chaos & Backoff: Resiliencia con fallos controlados

## Integrantes:

- Mora Evangelista, Fernando
- Osorio Tello, Jesus Diego

## Sprint 1

El objetivo del Sprint 1 fue cumplir con la primera fase del proyecto: "Modelo de reintentos/backoff + unit tests con parametrize".

El enfoque fue construir un sistema funcional de procesamiento de tareas basado en mensajería que pudiera manejar la lógica de reintentos en la capa de la API y sentar las bases para la inyección de caos en el Sprint 2.

### Estructura completa

1. **Modelo de Reintentos (Backoff)**:

    - Se implementó una API (FastAPI) que actúa como productor de mensajes.
    - Esta API utiliza un patrón Request-Reply para comunicarse con el Worker, esperando una confirmación síncrona.
    - Se implementó una función de reintentos con backoff exponencial (`resilience/retry.py`) que se activa si el Worker no responde a tiempo.

2. **Sistema de Procesamiento (Worker)**:

    - Se implementó un Worker que consume mensajes de RabbitMQ.
    - Se implementó un Adapter de base de datos (para Redis) siguiendo el Principio de Inversión de Dependencias (DIP).
    - El Worker ahora acepta mensajes JSON, procesa tareas (con delay simulado) y publica una respuesta en una cola de callback.

3. **Pruebas Unitarias Parametrizadas**:

    Se crearon tests unitarios (pytest) para todos los componentes clave.

    - `test_app.py`: Prueba la lógica de reintentos (client.call) con @pytest.mark.parametrize para los 3 casos límite:

        - Éxito al primer intento.
        - Éxito en el segundo intento (tras un fallo).
        - Fallo total tras 5 reintentos.

    - `test_worker.py`: Prueba que el worker procesa correctamente los mensajes JSON, usa el adapter y envía una respuesta.
    - `test_redis_repository.py`: Prueba la lógica del adapter de Redis en aislamiento.

4. Gestión y CI:

    - Se configuró un `Makefile` para estandarizar los comandos (test, lint, up, down, run-app, run-worker).
    - Se implementó un workflow básico de GitHub Actions (`ci.yml`) que instala dependencias y ejecuta pytest en cada push.

### Patrones Utilizados

- **Adapter(Adaptador)**: Se usó `ICounterRepository` (puerto) y `RedisCounterRepository` (adaptador) para desacoplar la lógica de la base de datos.
- **Mediator(Mediador)**: RabbitMQ actúa como un mediador. La App y el Worker no se conocen; solo se comunican a través del broker.
- **Command(Comando)**: Los mensajes JSON (`{"action": "INCREMENT", ...}`) actúan como comandos que encapsulan una solicitud.

### Ejemplo de uso

1. Levantar infraestructura

    Usamos el Makefile para iniciar los contenedores de Docker (RabbitMQ y Redis).

    ```bash
    make up
    ```

2. Iniciar los servicios

    - En un terminal iniciamos el worker
        ```bash
        make run-worker
        ```
    - En otro terminal iniciamos la app
        ```bash
        make run-app
        ```

3. Probamos nuesta app

    - Obtenemos el contador en otra terminal
        ```bash
        curl http://localhost:8000/api/counter/
        ```
    
    - Incrementamos el contador (3 veces con 0.5s de delay)
        ```bash
        curl -X POST "http://localhost:8000/api/counter/3?delay=0.5"
        ```

4. Verificamos los test

    ```bash
    make test
    ```
    
