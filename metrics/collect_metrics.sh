#!/bin/bash

# Script para recolectar métricas de la API Counter
# Uso: ./collect_metrics.sh [API_URL] [INTERVALO_SEGUNDOS]

API_URL="${1:-http://localhost:8000}"
INTERVAL="${2:-5}"
LOG_FILE="metrics_$(date +%Y%m%d_%H%M%S).log"


# Contadores
TOTAL_QUERIES=0
ERROR_RESPONSES=0
TOTAL_RETRIES=0
RETRY_COUNTS=()
DLQ_MESSAGES_START=0
DLQ_MESSAGES_CURRENT=0

echo "  Counter API - Metrics Collector"
echo "========================================="
echo "API URL: $API_URL"
echo "Interval: ${INTERVAL}s"
echo "Log file: $LOG_FILE"
echo "========================================="
echo ""

# Función para obtener mensajes en DLQ
get_dlq_count() {
    local response=$(curl -s "${API_URL}/api/dlq/stats" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "$response" | grep -o '"message_count":[0-9]*' | cut -d':' -f2
    else
        echo "0"
    fi
}

# Función para hacer una query y contar errores/retries
make_query() {
    local endpoint="$1"
    local method="${2:-GET}"
    
    TOTAL_QUERIES=$((TOTAL_QUERIES + 1))
    
    # Hacer request y capturar código de estado y tiempo
    local start_time=$(date +%s.%N)
    local response=$(curl -s -w "\n%{http_code}" -X "$method" "$endpoint" 2>/dev/null)
    local end_time=$(date +%s.%N)
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    local duration=$(echo "$end_time - $start_time" | bc)
    
    # Contar errores (status 5xx o 4xx)
    if [[ "$http_code" =~ ^[45] ]]; then
        ERROR_RESPONSES=$((ERROR_RESPONSES + 1))
        echo -e "[ERROR]HTTP $http_code - Query #$TOTAL_QUERIES" | tee -a "$LOG_FILE"
        
        # Intentar extraer información de retries del mensaje de error
        local retry_info=$(echo "$body" | grep -o 'after [0-9]* retries' | grep -o '[0-9]*')
        if [ -n "$retry_info" ]; then
            TOTAL_RETRIES=$((TOTAL_RETRIES + retry_info))
            RETRY_COUNTS+=($retry_info)
        fi
    else
        echo -e "$[OK]$ HTTP $http_code - Query #$TOTAL_QUERIES (${duration}s)" | tee -a "$LOG_FILE"
        
        # Si fue exitoso después de reintentos, contar retries estimados
        # (basado en el tiempo de respuesta vs tiempo normal)
        local expected_time=0.3
        if (( $(echo "$duration > 2" | bc -l) )); then
            local estimated_retries=$(echo "scale=0; ($duration - $expected_time) / 1" | bc)
            if [ "$estimated_retries" -gt 0 ]; then
                TOTAL_RETRIES=$((TOTAL_RETRIES + estimated_retries))
                RETRY_COUNTS+=($estimated_retries)
            fi
        fi
    fi
}

calculate_avg() {
    local sum=0
    local count=${#RETRY_COUNTS[@]}
    
    if [ $count -eq 0 ]; then
        echo "0"
        return
    fi
    
    for val in "${RETRY_COUNTS[@]}"; do
        sum=$((sum + val))
    done
    
    echo "scale=2; $sum / $count" | bc
}

# Función para mostrar métricas actuales
show_metrics() {
    clear
    echo "  MÉTRICAS EN TIEMPO REAL"
    echo "========================================="
    echo "Tiempo: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # Obtener DLQ actual
    DLQ_MESSAGES_CURRENT=$(get_dlq_count)
    local dlq_captured=$((DLQ_MESSAGES_CURRENT - DLQ_MESSAGES_START))
    
    # Calcular tasas
    local error_rate=0
    local dlq_rate=0
    local avg_retries=0
    
    if [ $TOTAL_QUERIES -gt 0 ]; then
        error_rate=$(echo "scale=2; ($ERROR_RESPONSES / $TOTAL_QUERIES) * 100" | bc)
        dlq_rate=$(echo "scale=2; ($dlq_captured / $TOTAL_QUERIES) * 100" | bc)
        avg_retries=$(calculate_avg)
    fi
    
    echo "CONTADORES:"
    echo "  • Total de consultas:     $TOTAL_QUERIES"
    echo "  • Respuestas con error:   $ERROR_RESPONSES"
    echo "  • Mensajes en DLQ:        $dlq_captured"
    echo "  • Total de retries:       $TOTAL_RETRIES"
    echo ""
    
    echo "TASAS:"
    if [ $TOTAL_QUERIES -gt 0 ]; then
        echo -e "  • Error rate:             ${error_rate}%"
        echo -e "  • Tasa captura DLQ:       ${dlq_rate}%"
    else
        echo "  • Error rate:             N/A"
        echo "  • Tasa captura DLQ:       N/A"
    fi
    echo ""
    
    echo "PROMEDIOS:"
    if [ ${#RETRY_COUNTS[@]} -gt 0 ]; then
        echo "  • Retries promedio:       ${avg_retries}"
    else
        echo "  • Retries promedio:       0"
    fi
    echo ""
    
    echo "ESTADO DLQ:"
    echo " Mensajes iniciales:     $DLQ_MESSAGES_START"
    echo " Mensajes actuales:      $DLQ_MESSAGES_CURRENT"
    echo " Capturados esta sesión: $dlg_captured"
    echo ""
    echo "========================================="
    echo "Presiona Ctrl+C para detener"
    echo "========================================="
}

save_final_report() {
    echo "" | tee -a "$LOG_FILE"
    echo "=========================================" | tee -a "$LOG_FILE"
    echo "  REPORTE FINAL" | tee -a "$LOG_FILE"
    echo "=========================================" | tee -a "$LOG_FILE"
    echo "Duración de la prueba: $(date)" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    
    local dlq_captured=$((DLQ_MESSAGES_CURRENT - DLQ_MESSAGES_START))
    local error_rate=0
    local dlq_rate=0
    local avg_retries=0
    
    if [ $TOTAL_QUERIES -gt 0 ]; then
        error_rate=$(echo "scale=2; ($ERROR_RESPONSES / $TOTAL_QUERIES) * 100" | bc)
        dlq_rate=$(echo "scale=2; ($dlq_captured / $TOTAL_QUERIES) * 100" | bc)
        avg_retries=$(calculate_avg)
    fi
    
    echo " CONTADORES FINALES:" | tee -a "$LOG_FILE"
    echo " Total de consultas:     $TOTAL_QUERIES" | tee -a "$LOG_FILE"
    echo " Respuestas con error:   $ERROR_RESPONSES" | tee -a "$LOG_FILE"
    echo " Mensajes en DLQ:        $dlq_captured" | tee -a "$LOG_FILE"
    echo " Total de retries:       $TOTAL_RETRIES" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    
    echo " TASAS FINALES:" | tee -a "$LOG_FILE"
    echo "  • Error rate:             ${error_rate}%" | tee -a "$LOG_FILE"
    echo "  • Tasa captura DLQ:       ${dlq_rate}%" | tee -a "$LOG_FILE"
    echo "  • Retries promedio:       ${avg_retries}" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    
    echo "=========================================" | tee -a "$LOG_FILE"
    echo "Reporte guardado en: $LOG_FILE"
}


trap 'echo ""; save_final_report; exit 0' INT

# Obtener DLQ inicial
DLQ_MESSAGES_START=$(get_dlq_count)

echo "Iniciando recolección de métricas..."
echo "Presiona Ctrl+C para detener y ver reporte final"
echo ""
sleep 2

# Loop principal
while true; do
    # Hacer algunas queries de prueba
    make_query "${API_URL}/api/counter/" "GET"
    
    make_query "${API_URL}/api/counter/5?delay=0.1" "POST"
    sleep 1
    
    # Mostrar métricas actualizadas
    show_metrics
    
    # Esperar intervalo
    sleep $INTERVAL
done