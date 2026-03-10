#!/usr/bin/env bash
# Monitora o nível do microfone em tempo real (VU meter no terminal).
# Útil para calibrar os thresholds de detecção de silêncio do sox.
#
# Uso:
#   bash test_mic_level.sh [THRESHOLD_%]
#   bash test_mic_level.sh 2
#
# Pressione Ctrl+C para sair.

SAMPLE_RATE=16000
THRESHOLD="${1:-2}"    # threshold padrão = 2% (mesmo do client.sh)
BAR_WIDTH=40
CHUNK_BYTES=3200       # 100ms a 16kHz 16-bit mono

echo "=== Monitor de Nível do Microfone ==="
echo "  Threshold: ${THRESHOLD}%  (a linha | no bar)"
echo "  Ctrl+C para sair"
echo ""

arecord \
    --format=S16_LE \
    --rate="$SAMPLE_RATE" \
    --channels=1 \
    --quiet \
    --file-type raw 2>/dev/null \
| while true; do
    # Lê um chunk de 100ms e extrai RMS via sox stat
    RMS=$(dd bs="$CHUNK_BYTES" count=1 iflag=fullblock 2>/dev/null \
          | sox -t raw -r "$SAMPLE_RATE" -c 1 -b 16 -e signed-integer - -n stat 2>&1 \
          | awk '/RMS.*amplitude/ { print $3 }')

    [ -z "$RMS" ] && continue

    # Calcula barra e status em awk (sem bc ou python)
    awk -v rms="$RMS" -v thr="$THRESHOLD" -v w="$BAR_WIDTH" 'BEGIN {
        pct    = rms * 100
        filled = int(pct * w / 100)
        if (filled > w) filled = w
        tpos   = int(thr * w / 100)

        bar = ""
        for (i = 0; i < w; i++) {
            if      (i == tpos)   bar = bar "|"
            else if (i < filled)  bar = bar "#"
            else                  bar = bar "-"
        }

        status = (pct >= thr) ? "FALA  " : "silenc"
        printf "\r  [%s] %5.1f%%  [%s]", bar, pct, status
    }'
done

echo ""
