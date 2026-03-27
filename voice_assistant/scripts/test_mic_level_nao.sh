#!/usr/bin/env bash

set -euo pipefail

SAMPLE_RATE="${SAMPLE_RATE:-16000}"
CHANNELS="${CHANNELS:-1}"
BIT_DEPTH="${BIT_DEPTH:-16}"
ALSA_DEVICE="${ALSA_DEVICE:-default}"
THRESHOLD="${1:-${THRESHOLD:-4}}"
BAR_WIDTH="${BAR_WIDTH:-50}"
CHUNK_MS="${CHUNK_MS:-100}"
CHUNK_BYTES=$(( SAMPLE_RATE * CHANNELS * (BIT_DEPTH / 8) * CHUNK_MS / 1000 ))

check_dep() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERRO: '$1' nao encontrado. Instale com: sudo apt install $2" >&2
        exit 1
    fi
}

check_dep arecord alsa-utils
check_dep sox sox
check_dep awk gawk
check_dep dd coreutils

cleanup() {
    printf '\n'
}
trap cleanup EXIT

printf '=== Monitor de Nivel do Microfone (NAO) ===\n'
printf 'Dispositivo ALSA: %s\n' "$ALSA_DEVICE"
printf 'Threshold inicial: %s%%\n' "$THRESHOLD"
printf 'Chunk: %sms | Ctrl+C para sair\n\n' "$CHUNK_MS"

arecord \
    -D "$ALSA_DEVICE" \
    --format=S16_LE \
    --rate="$SAMPLE_RATE" \
    --channels="$CHANNELS" \
    --quiet \
    --file-type raw 2>/dev/null \
| while true; do
    RMS=$(dd bs="$CHUNK_BYTES" count=1 iflag=fullblock 2>/dev/null \
        | sox \
            -t raw \
            -r "$SAMPLE_RATE" \
            -c "$CHANNELS" \
            -b "$BIT_DEPTH" \
            -e signed-integer \
            - \
            -n stat 2>&1 \
        | awk '/RMS.*amplitude/ { print $3; exit }')

    [ -z "$RMS" ] && continue

    awk \
        -v rms="$RMS" \
        -v thr="$THRESHOLD" \
        -v w="$BAR_WIDTH" \
        'BEGIN {
            level = rms * 100
            if (level < 0) level = 0
            if (level > 100) level = 100

            filled = int(level * w / 100)
            if (filled > w) filled = w

            tpos = int(thr * w / 100)
            if (tpos < 0) tpos = 0
            if (tpos >= w) tpos = w - 1

            status = (level >= thr) ? "FALA" : "silencio"

            bar = ""
            for (i = 0; i < w; i++) {
                if (i == tpos) {
                    bar = bar "|"
                } else if (i < filled) {
                    bar = bar "#"
                } else {
                    bar = bar "-"
                }
            }

            printf "\r[%s] nivel=%5.2f%% threshold=%5.2f%% [%s]   ", bar, level, thr, status
            fflush()
        }'
done
