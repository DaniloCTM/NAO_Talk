#!/usr/bin/env bash

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------
SERVER_HOST="${1:-${SERVER_HOST:-10.0.69.12}}"
SERVER_PORT="${2:-${SERVER_PORT:-50007}}"

SAMPLE_RATE=16000
CHANNELS=1
BIT_DEPTH=16
ALSA_DEVICE="${ALSA_DEVICE:-default}"

# VAD: threshold de amplitude para considerar fala (em %)
SPEECH_THRESHOLD="${SPEECH_THRESHOLD:-2}"
# Duracao minima de fala para iniciar gravacao (segundos)
SPEECH_START_DURATION="${SPEECH_START_DURATION:-0.1}"
# Duracao de silencio para encerrar gravacao (segundos)
SILENCE_DURATION="${SILENCE_DURATION:-1.5}"
# Threshold de silencio (em %) -- geralmente igual ao de fala
SILENCE_THRESHOLD="${SILENCE_THRESHOLD:-2}"

TMP_OUT="/tmp/va_response_$$.wav"

cleanup() {
    rm -f "$TMP_OUT"
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

record_and_send_receive() {
    echo "Aguardando fala... (threshold: ${SPEECH_THRESHOLD}%, silencio: ${SILENCE_DURATION}s)"
    echo "Transmitindo audio por pipe para ${SERVER_HOST}:${SERVER_PORT}"

    {
        arecord \
            -D "$ALSA_DEVICE" \
            --format=S16_LE \
            --rate="$SAMPLE_RATE" \
            --channels="$CHANNELS" \
            --quiet \
            --file-type raw 2>/dev/null || true
    } \
    | sox \
        --type raw \
        --rate "$SAMPLE_RATE" \
        --channels "$CHANNELS" \
        --bits "$BIT_DEPTH" \
        --encoding signed-integer \
        - \
        --type wav \
        - \
        silence \
            1 "$SPEECH_START_DURATION" "${SPEECH_THRESHOLD}%" \
            1 "$SILENCE_DURATION" "${SILENCE_THRESHOLD}%" \
        2>/dev/null \
    | nc -N "$SERVER_HOST" "$SERVER_PORT" > "$TMP_OUT" 2>/dev/null
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
echo "VAD: inicio=${SPEECH_THRESHOLD}% por ${SPEECH_START_DURATION}s | silencio=${SILENCE_THRESHOLD}% por ${SILENCE_DURATION}s"
echo "Modo de envio: WAV por pipe direto para o servidor TCP"

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

    T_CYCLE_START=$(now_ms)

    if ! record_and_send_receive; then
        echo "Erro de gravacao ou comunicacao com o servidor"
        continue
    fi

    T_RESPONSE_END=$(now_ms)

    if [ ! -s "$TMP_OUT" ]; then
        echo "Sem resposta do servidor"
        continue
    fi

    SIZE_OUT=$(wc -c < "$TMP_OUT")
    PIPE_MS=$(( T_RESPONSE_END - T_CYCLE_START ))

    echo "Resposta recebida (${SIZE_OUT} bytes, ${PIPE_MS}ms)"

    play_response

    TOTAL_MS=$(( T_RESPONSE_END - T_CYCLE_START ))
    echo "Ciclo completo em ${TOTAL_MS}ms"
done
