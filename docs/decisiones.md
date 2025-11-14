# Proyecto 7: Chaos & Backoff

Este documento describe las decisiones de arquitectura, los patrones de diseño aplicados y las políticas de calidad para el proyecto, como se define en el enunciado de esta PC.

## 1. Visión de la Arquitectura

El sistema está diseñado como una arquitectura desacoplada basada en los incrementos de un contador de forma resiliente.

Los componentes principales son:

- **App(API)**: Un productor de mensajes (FastAPI) que expone endpoints HTTP al usuario. Es responsable de la lógica de reintentos del lado del cliente.

- **Broker(Mediador)**: Un bus de mensajería (RabbitMQ) que desacopla la API de los workers.

- **Worker**: Un consumidor de mensajes que ejecuta la lógica de la tarea y se comunica con la base de datos.

- **Base de Datos (Target)**: Un almacén de estado (Redis) que guarda el contador.

## 2. Patrones de Diseño Aplicados
Para cumplir con los requisitos técnicos, se han implementado los siguientes patrones:

- **Mediator(Mediador)**: RabbitMQ actúa como el mediador central. La App y el Worker no interactúan directamente; solo publican o consumen mensajes del broker. Esto permite que el worker falle o se reinicie sin afectar a la API.

- **Adapter(Adaptador)**: La lógica de la base de datos está encapsulada.

    - **Puerto(Interface)**: `src/ports/repository.py` define la abstracción `ICounterRepository`.
    - **Adaptador(Implementación)**: `src/adapters/redis_repository.py` es la implementación que adapta la interfaz a los comandos de Redis.

- **Command(Comando)**: Los mensajes JSON enviados al broker siguen el patrón Command. Cada mensaje es un objeto (ej. `{"action": "INCREMENT_COUNTER", ...}`) que encapsula toda la información necesaria para ejecutar una acción.

## 3. Decisiones Clave de Diseño
Estas son las decisiones de arquitectura fundamentales tomadas para el proyecto.

### Comunicación por Request-Reply (RPC)

- Decisión: Implementar un patrón de "Solicitud-Respuesta" (RPC) sobre RabbitMQ.
- Justificación: La App (API) necesita devolver una respuesta síncrona al usuario (ej. {"status": "ok", "counter": 3}). Para lograr esto, la API publica un mensaje con un reply_to (una cola de respuesta temporal) y un correlation_id. El Worker procesa la tarea y envía su resultado de vuelta a esa cola específica.

### Lógica de Resiliencia (Backoff) en el Cliente

- Decisión: La lógica de reintentos y backoff exponencial se implementará en el cliente (la App), no en el worker.
- Justificación: Esto cumple con el objetivo del Sprint 1. Si el Worker no responde a la App dentro de un tiempo límite (porque está caído, lento o en medio de un caos), la App es responsable de reintentar la solicitud. Esto se maneja en src/resilience/retry.py.

### Infraestructura como Código (IaC) con Terraform

- Decisión: Toda la infraestructura local (Broker, DB) se gestionará con Terraform.
- Justificación: Garantiza un entorno de desarrollo reproducible e idempotente para todos los miembros del equipo.

## 4. Políticas de Calidad y CI

- Pruebas Unitarias: Todo nuevo componente lógico (ej. app, worker, adapter) debe estar cubierto por pruebas unitarias (pytest).
- Pruebas de Lógica de Negocio: La lógica de resiliencia (retry) debe ser probada con casos límite parametrizados (@pytest.mark.parametrize).
- Formato de Código: Se utiliza black para mantener un estilo de código consistente.
- Integración Continua (CI): El pipeline de GitHub Actions (.github/workflows/ci.yml) debe pasar antes de que cualquier PR pueda ser mergeado a main o develop. El pipeline es responsable de instalar dependencias y ejecutar los test.