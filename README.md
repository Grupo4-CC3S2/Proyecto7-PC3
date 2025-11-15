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
    
### Sprint 2 - Fernando Mora

El objetivo del Sprint 2 fue cumplir con la segunda fase del proyecto: "Inyección de caos".
Se implementaron mecanismos para simular fallos en el Worker y la App, evaluando la resiliencia del sistema bajo condiciones adversas.
Se añadieron las siguientes funcionalidades:

1. **Inyección de Caos en el Worker**:
    - Se implementó una `ChaosMixin` que introduce fallos aleatorios en el procesamiento de mensajes del Worker en base a una tasa de fallo configurable mediante la variable de entorno `CHAOS_RATE`.
    - El Worker ahora puede simular excepciones durante la ejecución de comandos, permitiendo probar la capacidad de recuperación del sistema.
2. **Backoff en la App**:
    - Se mejoró la lógica de reintentos en la App para manejar los fallos inducidos por el Worker.
    - La App ahora puede reintentar solicitudes fallidas al Worker, utilizando un backoff exponencial para evitar sobrecargar el sistema.
3. **Dead Letter Queue (DLQ)**:
    - Se implementó una DLQ en RabbitMQ para manejar mensajes que no pudieron ser procesados después de varios intentos.
    - Los mensajes fallidos se redirigen a la DLQ, permitiendo su análisis posterior y evitando la pérdida de datos.
    - Se puede consular la cantidad de mensajes en la DLQ mediante el endpoint `/api/dlq/stats`.

## Sprint 2 - Jesus Osorio

Me encargué de construir, automatizar y validar la plataforma de infraestructura y el pipeline de calidad para que estas pruebas de caos fueran posibles y medibles.

- Hice que Terraform despliegue todo el stack.

    - Dockerización: Creé `Dockerfile.app` y `Dockerfile.worker` para empaquetar las aplicaciones de Python.
    - Modifiqué `main.tf` para crear una docker_network. Los 4 contenedores (app, worker, broker, db) se despliegan en esta red y se comunican usando sus nombres de contenedor (chaos-broker, chaos-db).
    - El `main.tf` ahora pasa estos nombres de host como variables de entorno (env = [...]) a los contenedores.
    - Modifiqué `worker.py` y `redis_repository.py` para leer estas variables de entorno (os.getenv).

- Para asegurar la calidad, implementé las puertas de validación.

    - Cobertura de Pruebas (>85%):

        - Añadí tests unitarios para cubrir todos los casos de error que faltaban en `app.py`, `worker.py` y los módulos de commands.
        - Esto incluyó probar la lógica de compensación, el rechazo de mensajes para la DLQ y todos los try...except de la API.
        - Modifiqué `make test` para fallar si la cobertura es < 85%. Alcanzamos un 86%.

    - Validación de IaC:

        - Creé el target `make lint-iac` en el Makefile, que agrupa `terraform fmt --check`, `validate` y `tflint`.

    - Pipeline de CI Completo:

        - Actualicé `.github/workflows/ci.yml` para instalar Terraform.
        - El pipeline ahora ejecuta `make test` y `make lint-iac`, además de un step separado para `tfsec`.

### Ejemplo de uso

1. Construimos las imágenes

```bash
make build
```

2. Desplegar el sistema completo

```bash
make up
```

3. Prueba de camino feliz (API) 

```bash
curl http://localhost:8000/api/counter/
```

4. Probamos la lógica de rechazo que fusionamos en `worker.py`.

    - Abrir la UI: Vamos a `http://localhost:15673` (UI de RabbitMQ).
    - Verificamos Colas: Ve a "Queues" y confirma que tasks_queue y tasks_queue_dlq existen.
    - Inyectar Mensaje Erróneo:
        - Hacemos clic en tasks_queue.
        - Vamos a "Publish message".
        - Publicamos un mensaje con una acción que no existe: `{"action": "ACCION_INVALIDA"}`.

    - Vemos el Resultado: Refrescamos la página. El mensaje desaparece de `tasks_queue` y aparece 1 mensaje nuevo en `tasks_queue_dlq`. ¡El mensaje fallido fue capturado!

## Sprint 3 - Mora

# 1. Script de Métricas: `collect_metrics.sh`

Este script permite ejecutar una sesión de medición continua sobre la API Counter, recolectando estadísticas clave y generando un reporte final al finalizar la prueba.

## Funcionalidades principales

### Recolección continua de métricas
- Número total de consultas enviadas.
- Cantidad de respuestas con error (4xx/5xx).
- Retries detectados explícitamente en las respuestas.
- Retries estimados según el tiempo de ejecución.
- Mensajes capturados en la Dead Letter Queue (DLQ).

### Panel interactivo en tiempo real
En cada iteración, se muestra un tablero con:
- Contadores acumulados.
- Tasas de error.
- Tasa de captura en DLQ.
- Retries totales y promedio.
- Estado inicial y actual de la DLQ.

### Registro completo en archivos
Cada ejecución genera un archivo con nombre:

```
metrics_YYYYMMDD_HHMMSS.log
```

# 2. Integración con Makefile

Se añadió el target:

```
make metrics
```

Este comando ejecuta el recolector con los parámetros por defecto y simplifica las pruebas manuales o automatizadas del sistema durante escenarios de caos.

Se creó un archivo en `docs/metrics.md` con los resultados obtenidos al ejecutar pruebas bajo distintos niveles de fallo controlado:

- CHAOS_RATE = 0.1
- CHAOS_RATE = 0.4