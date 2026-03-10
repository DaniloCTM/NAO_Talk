#!/usr/bin/env bash

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
SERVER_HOST="${1:-${SERVER_HOST:-10.0.69.12}}"
SERVER_PORT="${2:-${SERVER_PORT:-50007}}"

SAMPLE_RATE=16000
CHANNELS=1
BIT_DEPTH=16

# VAD: threshold de amplitude para considerar fala (em %)
SPEECH_THRESHOLD="${SPEECH_THRESHOLD:-2}"
# Duração mínima de fala para iniciar gravação (segundos)
SPEECH_START_DURATION="${SPEECH_START_DURATION:-0.1}"
# Duração de silêncio para encerrar gravação (segundos)
SILENCE_DURATION="${SILENCE_DURATION:-1.5}"
# Threshold de silêncio (em %) — geralmente igual ao de fala
SILENCE_THRESHOLD="${SILENCE_THRESHOLD:-2}"

TMP_IN="/tmp/va_input_$$.wav"
TMP_OUT="/tmp/va_response_$$.wav"

cleanup() {
    rm -f "$TMP_IN" "$TMP_OUT"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Dependências
# ---------------------------------------------------------------------------
check_dep() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERRO: '$1' não encontrado. Instale com: sudo apt install $2" >&2
        exit 1
    fi
}

check_dep arecord alsa-utils
check_dep aplay   alsa-utils
check_dep sox     sox
check_dep nc      netcat-openbsd

# ---------------------------------------------------------------------------
# Funções
# ---------------------------------------------------------------------------

check_server() {
    nc -z -w 2 "$SERVER_HOST" "$SERVER_PORT" 2>/dev/null
}

record_audio() {
    echo "Aguardando fala... (threshold: ${SPEECH_THRESHOLD}%, silêncio: ${SILENCE_DURATION}s)"

    # Watcher em background: avisa quando o arquivo de saída crescer além do
    # cabeçalho WAV (44 bytes), o que indica que sox começou a gravar fala.
    (
        while true; do
            local size
            size=$(wc -c < "$TMP_IN" 2>/dev/null || echo 0)
            if [ "$size" -gt 44 ]; then
                echo "Fala detectada!"
                break
            fi
            sleep 0.1
        done
    ) &
    local WATCHER_PID=$!

    # sox silence: aguarda fala e grava até detectar silêncio automaticamente.
    #   silence 1 <dur_inicio> <thr_inicio>%  1 <dur_fim> <thr_fim>%
    #   - 1 período acima de SPEECH_THRESHOLD% por SPEECH_START_DURATION s → inicia
    #   - 1 período abaixo de SILENCE_THRESHOLD% por SILENCE_DURATION s    → encerra
    { arecord \
        --format=S16_LE \
        --rate="$SAMPLE_RATE" \
        --channels="$CHANNELS" \
        --quiet \
        --file-type raw 2>/dev/null || true; } \
    | sox \
        --type raw \
        --rate "$SAMPLE_RATE" \
        --channels "$CHANNELS" \
        --bits "$BIT_DEPTH" \
        --encoding signed-integer \
        - \
        "$TMP_IN" \
        silence \
            1 "$SPEECH_START_DURATION" "${SPEECH_THRESHOLD}%" \
            1 "$SILENCE_DURATION"      "${SILENCE_THRESHOLD}%" \
        2>/dev/null

    kill "$WATCHER_PID" 2>/dev/null || true
    wait "$WATCHER_PID" 2>/dev/null || true

    echo "Gravação finalizada"
}

send_and_receive() {
    nc -N "$SERVER_HOST" "$SERVER_PORT" < "$TMP_IN" > "$TMP_OUT" 2>/dev/null
}

play_response() {
    echo "Reproduzindo resposta..."
    aplay --quiet "$TMP_OUT"
}

now_ms() {
    date +%s%3N
}

# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

echo "=== Assistente de Voz (cliente bash) ==="
echo "Servidor: $SERVER_HOST:$SERVER_PORT"
echo "VAD: início=${SPEECH_THRESHOLD}% por ${SPEECH_START_DURATION}s | silêncio=${SILENCE_THRESHOLD}% por ${SILENCE_DURATION}s"

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
    rm -f "$TMP_IN" "$TMP_OUT"

    echo ""
    echo "=== Novo ciclo ==="

    T_RECORD_START=$(now_ms)

    if ! record_audio; then
        echo "Erro na gravação"
        continue
    fi

    T_RECORD_END=$(now_ms)

    if [ ! -s "$TMP_IN" ]; then
        echo "Nenhum áudio capturado"
        continue
    fi

    SIZE_IN=$(wc -c < "$TMP_IN")
    RECORD_MS=$(( T_RECORD_END - T_RECORD_START ))

    echo "Gravação concluída (${SIZE_IN} bytes, ${RECORD_MS}ms)"
    echo "Enviando para servidor..."

    T_NET_START=$(now_ms)

    if ! send_and_receive; then
        echo "Erro de comunicação com servidor"
        continue
    fi

    T_NET_END=$(now_ms)

    if [ ! -s "$TMP_OUT" ]; then
        echo "Sem resposta do servidor"
        continue
    fi

    NET_MS=$(( T_NET_END - T_NET_START ))
    echo "Resposta recebida (${NET_MS}ms)"

    play_response

    TOTAL_MS=$(( T_NET_END - T_RECORD_START ))
    echo "Ciclo completo em ${TOTAL_MS}ms"
done
