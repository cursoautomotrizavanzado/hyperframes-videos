# autodiag-hyperframes-engine

Motor de render de **AutoDiag Video Studio**. Lo crea y actualiza automáticamente el botón **🚀 Auto-Configurar mi Nube** de la app; no hace falta tocar nada aquí.

Flujo de cada video (GitHub Actions, `render_video.yml`):

1. `jobs/<id>.json` (guion + escenas) llega desde la app y se lanza el flujo con `job_id`.
2. `render/prepare_audio.py` genera la voz con Edge-TTS (o transcribe tu audio con Whisper) → `timeline.json` palabra por palabra.
3. `render/build_composition.js` arma la composición HyperFrames (`index.html`, Canvas 2D sincronizado con la voz).
4. `npx hyperframes render` captura los cuadros (respaldo: `render/capture_fallback.js` con Puppeteer).
5. `render/finalize.js` une voz + video con FFmpeg e incrusta la portada.
6. El MP4 se publica en la rama temporal `render-<id>`; la app lo descarga y la borra.

Alternativas: `Dockerfile` + `server/server.js` (Render.com, botón *Deploy to Render* usa `render.yaml`) y `worker/worker.js` (proxy Cloudflare que guarda tu token en el servidor).
