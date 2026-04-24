#!/usr/bin/env bash

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------
SERVER_HOST="${1:-${SERVER_HOST:-10.0.69.12}}"
SERVER_PORT="${2:-${SERVER_PORT:-50007}}"

SAMPLE_RATE=16000
BIT_DEPTH=16
ALSA_DEVICE="${ALSA_DEVICE:-default}"
CAPTURE_CHANNELS="${CAPTURE_CHANNELS:-4}"
OUTPUT_CHANNELS=1
CHANNEL_REMIX="${CHANNEL_REMIX:--}"
TRANSPORT_MODE="${TRANSPORT_MODE:-tcp-stream}"

# VAD: threshold de amplitude para considerar fala (em %)
SPEECH_THRESHOLD="${SPEECH_THRESHOLD:-2}"
# Duracao minima de fala para iniciar gravacao (segundos)
SPEECH_START_DURATION="${SPEECH_START_DURATION:-0.1}"
# Duracao de silencio para encerrar gravacao (segundos)
SILENCE_DURATION="${SILENCE_DURATION:-0.8}"
# Threshold de silencio (em %) -- geralmente igual ao de fala
SILENCE_THRESHOLD="${SILENCE_THRESHOLD:-2}"

TMP_OUT="/tmp/va_response_$$.wav"
TMP_STREAM_IN="/tmp/va_request_$$.fifo"
TMP_CAPTURE_END="/tmp/va_capture_end_$$.txt"
CAPTURE_PID=""
CLIENT_CAPTURE_MS=0
CLIENT_SEND_RECEIVE_MS=0
CLIENT_CYCLE_MS=0

cleanup() {
    if [ -n "${CAPTURE_PID:-}" ] && kill -0 "$CAPTURE_PID" 2>/dev/null; then
        kill "$CAPTURE_PID" 2>/dev/null || true
    fi
    rm -f "$TMP_OUT" "$TMP_STREAM_IN" "$TMP_CAPTURE_END"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Dependencias
# ---------------------------------------------------------------------------
check_dep() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERRO: '$1' nao encontrado. Instale com: sudo apt install $2" >&2
        exit 1
    fi
}

check_dep arecord alsa-utils
check_dep aplay alsa-utils
check_dep sox sox
check_dep nc netcat-openbsd

# ---------------------------------------------------------------------------
# Funcoes
# ---------------------------------------------------------------------------

check_server() {
    nc -z -w 2 "$SERVER_HOST" "$SERVER_PORT" 2>/dev/null
}

transport_output_type() {
    case "$TRANSPORT_MODE" in
        tcp-stream) echo "raw" ;;
        tcp-wav) echo "wav" ;;
        *)
            echo "ERRO: TRANSPORT_MODE invalido: $TRANSPORT_MODE (use tcp-stream ou tcp-wav)" >&2
            return 1
            ;;
    esac
}

capture_audio() {
    local output_type="$1"

    {
        arecord \
            -D "$ALSA_DEVICE" \
            --format=S16_LE \
            --rate="$SAMPLE_RATE" \
            --channels="$CAPTURE_CHANNELS" \
            --quiet \
            --file-type raw 2>/dev/null || true
    } \
    | sox \
        --type raw \
        --rate "$SAMPLE_RATE" \
        --channels "$CAPTURE_CHANNELS" \
        --bits "$BIT_DEPTH" \
        --encoding signed-integer \
        - \
        --type "$output_type" \
        - \
        remix "$CHANNEL_REMIX" \
        channels "$OUTPUT_CHANNELS" \
        silence \
            1 "$SPEECH_START_DURATION" "${SPEECH_THRESHOLD}%" \
            1 "$SILENCE_DURATION" "${SILENCE_THRESHOLD}%" \
        2>/dev/null
}

start_capture_writer() {
    local output_type="$1"

    rm -f "$TMP_STREAM_IN" "$TMP_CAPTURE_END"
    mkfifo "$TMP_STREAM_IN"

    (
        local status=0
        capture_audio "$output_type" > "$TMP_STREAM_IN" || status=$?
        now_ms > "$TMP_CAPTURE_END"
        exit "$status"
    ) &
    CAPTURE_PID=$!
}

record_and_send_receive() {
    local output_type
    local t_cycle_start
    local t_response_end
    local t_capture_end
    local capture_status=0

    output_type="$(transport_output_type)" || return 1

    echo "Aguardando fala... (threshold: ${SPEECH_THRESHOLD}%, silencio: ${SILENCE_DURATION}s)"
    echo "Transmitindo audio por pipe para ${SERVER_HOST}:${SERVER_PORT} (${TRANSPORT_MODE})"

    t_cycle_start=$(now_ms)
    CLIENT_CAPTURE_MS=0
    CLIENT_SEND_RECEIVE_MS=0
    CLIENT_CYCLE_MS=0

    start_capture_writer "$output_type"

    if ! nc -N "$SERVER_HOST" "$SERVER_PORT" < "$TMP_STREAM_IN" > "$TMP_OUT" 2>/dev/null; then
        if [ -n "${CAPTURE_PID:-}" ]; then
            wait "$CAPTURE_PID" || true
            CAPTURE_PID=""
        fi
        rm -f "$TMP_STREAM_IN"
        return 1
    fi

    if [ -n "${CAPTURE_PID:-}" ]; then
        if wait "$CAPTURE_PID"; then
            capture_status=0
        else
            capture_status=$?
        fi
    fi
    CAPTURE_PID=""

    t_response_end=$(now_ms)
    t_capture_end="$t_response_end"
    if [ -s "$TMP_CAPTURE_END" ]; then
        read -r t_capture_end < "$TMP_CAPTURE_END" || t_capture_end="$t_response_end"
    fi

    CLIENT_CAPTURE_MS=$(( t_capture_end - t_cycle_start ))
    CLIENT_SEND_RECEIVE_MS=$(( t_response_end - t_capture_end ))
    CLIENT_CYCLE_MS=$(( t_response_end - t_cycle_start ))

    rm -f "$TMP_STREAM_IN" "$TMP_CAPTURE_END"
    return "$capture_status"
}

play_response() {
    echo "Reproduzindo resposta..."
    aplay --quiet "$TMP_OUT"
}

now_ms() {
    date +%s%3N
}

# ---------------------------------------------------------------------------
# Inicializacao
# ---------------------------------------------------------------------------

echo "=== Assistente de Voz (cliente bash TCP) ==="
echo "Servidor: $SERVER_HOST:$SERVER_PORT"
echo "Dispositivo ALSA: $ALSA_DEVICE"
echo "Captura: ${CAPTURE_CHANNELS} canais | envio: ${OUTPUT_CHANNELS} canal | remix: ${CHANNEL_REMIX}"
echo "VAD: inicio=${SPEECH_THRESHOLD}% por ${SPEECH_START_DURATION}s | silencio=${SILENCE_THRESHOLD}% por ${SILENCE_DURATION}s"
echo "Modo de envio: ${TRANSPORT_MODE}"

echo -n "Verificando servidor... "
if check_server; then
    echo "OK"
else
    echo "FALHOU (continuando mesmo assim)"
fi
echo ""

# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

while true; do
    rm -f "$TMP_OUT"

    echo ""
    echo "=== Novo ciclo ==="

    if ! record_and_send_receive; then
        echo "Erro de gravacao ou comunicacao com o servidor"
        continue
    fi

    if [ ! -s "$TMP_OUT" ]; then
        echo "Sem resposta do servidor"
        continue
    fi

    SIZE_OUT=$(wc -c < "$TMP_OUT")

    echo "Resposta recebida (${SIZE_OUT} bytes, capture=${CLIENT_CAPTURE_MS}ms, send_receive=${CLIENT_SEND_RECEIVE_MS}ms, cycle=${CLIENT_CYCLE_MS}ms)"

    play_response

    echo "Ciclo completo em ${CLIENT_CYCLE_MS}ms"
done
