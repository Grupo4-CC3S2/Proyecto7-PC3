# Documentación - Recolector de Métricas bajo Chaos Engineering

## Descripción General

El script `collect_metrics.sh` permite monitorear el comportamiento del sistema Counter API bajo diferentes condiciones de fallo simuladas mediante Chaos Engineering. Esta documentación detalla los resultados obtenidos con diferentes tasas de caos (`CHAOS_RATE`).

## Configuración del Entorno de Pruebas

### Arquitectura
```
[collect_metrics.sh] -> [API FastAPI] <--RPC--> [RabbitMQ] <---> [Worker con Chaos]
```

### Variables de Entorno del Worker
```bash
CHAOS_RATE=0.40  # Tasa de fallos aleatorios (0.0 - 1.0)
MAX_RETRIES=4    # Número máximo de reintentos
```

### Ejecución del Script
```bash
make metrics
```

---

## Escenario 1: Alta Tasa de Caos (CHAOS_RATE=0.40)

### Configuración
```bash
CHAOS_RATE=0.40  # 40% de probabilidad de fallo aleatorio
MAX_RETRIES=4
```

### Resultados Obtenidos

```
=========================================
  REPORTE FINAL
=========================================
Duración de la prueba: Sat Nov 15 01:29:12 AM -05 2025

CONTADORES FINALES:
  • Total de consultas:     106
  • Respuestas con error:   42
  • Mensajes en DLQ:        42
  • Total de retries:       216

TASAS FINALES:
  • Error rate:             39.00%
  • Tasa captura DLQ:       39.00%
  • Retries promedio:       3.07

=========================================
```

### Análisis de Resultados

#### Comportamiento del Sistema
- **Error Rate**: 39.00% - Muy cercano al CHAOS_RATE configurado (40%), demostrando que el sistema está correctamente simulando fallos
- **Tasa de Captura DLQ**: 39.00% - Excelente correlación, todos los errores permanentes fueron capturados
- **Retries Promedio**: 3.07 - Ligeramente inferior al máximo (3).

## Escenario 2: Baja Tasa de Caos (CHAOS_RATE=0.10)

### Configuración
```bash
CHAOS_RATE=0.10  # 10% de probabilidad de fallo aleatorio
MAX_RETRIES=4
```

### Resultados Obtenidos

```
=========================================
  REPORTE FINAL
=========================================
Duración de la prueba: Sat Nov 15 01:41:36 AM -05 2025

CONTADORES FINALES:
  • Total de consultas:     124
  • Respuestas con error:   3
  • Mensajes en DLQ:        3
  • Total de retries:       68

TASAS FINALES:
  • Error rate:             2.00%
  • Tasa captura DLQ:       2.00%
  • Retries promedio:       2.80

=========================================
```

### Análisis de Resultados

#### Comportamiento del Sistema
- **Error Rate**: 2.00% - Significativamente inferior al CHAOS_RATE (10%), indicando que el mecanismo de retry está funcionando efectivamente
- **Tasa de Captura DLQ**: 2.00% - Solo los errores verdaderamente permanentes llegan a DLQ
- **Retries Promedio**: 2.80 - Esperado debido a la baja tasa de fallos

### Observaciones Clave

1. **Linealidad del Error Rate**: El error rate es aproximadamente proporcional al CHAOS_RATE, pero el retry con backoff reduce significativamente los errores finales

3. **Eficiencia Inversa**: A menor CHAOS_RATE, mayor eficiencia del retry

