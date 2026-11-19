#!/usr/bin/env bash
# Pipeline completo: Guion -> Voz -> Timestamps -> Composición HTML -> HyperFrames -> FFmpeg (MP4 con audio y portada)
# Uso: bash render/pipeline.sh <job.json> <carpeta_salida> [audio_subido]
set -euo pipefail
JOB="$1"; OUT="$2"; AUDIO="${3:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT"
FPS=$(node -e "const j=require(require('path').resolve('$JOB'));console.log(j.fps||60)")
echo "::group::1/4 Voz y marcas de tiempo"
python3 "$HERE/prepare_audio.py" "$JOB" "$OUT" "$AUDIO"
echo "::endgroup::"
echo "::group::2/4 Composición HTML"
node "$HERE/build_composition.js" "$JOB" "$OUT/timeline.json" "$OUT/project"
echo "::endgroup::"
echo "::group::3/4 Render de cuadros (HyperFrames)"
if [ "${AUTODIAG_FORCE_FALLBACK:-0}" != "1" ] && npx --no-install hyperframes render "$OUT/project" -o "$OUT/muda.mp4" --fps "$FPS" -q standard; then
  echo "[render] HyperFrames OK"
else
  echo "[render] HyperFrames no disponible o falló: usando captura de respaldo Puppeteer"
  node "$HERE/capture_fallback.js" "$OUT/project/index.html" "$OUT/muda.mp4" "$FPS"
fi
echo "::endgroup::"
echo "::group::4/4 Diseño sonoro + mezcla de audio y video (FFmpeg)"
SFX=""
if node "$HERE/events.js" "$OUT/project/index.html" "$OUT/events.json" && [ -s "$OUT/events.json" ] && \
   node -e "process.exit(require(require('path').resolve('$OUT/events.json')).sonido===false?1:0)" && \
   python3 "$HERE/sfx.py" "$OUT/events.json" "$OUT/sfx.wav"; then SFX="$OUT/sfx.wav"; fi
node "$HERE/finalize.js" "$OUT/muda.mp4" "$OUT/voz.mp3" "$OUT/final.mp4" "$SFX"
echo "::endgroup::"
ls -la "$OUT/final.mp4"
