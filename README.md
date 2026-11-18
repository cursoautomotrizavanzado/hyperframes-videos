# AutoDiag Video Studio · Multi-User Edition

| Carpeta | Qué es |
|---|---|
| `cloud/` | Motor en la nube que el Auto-Instalador sube al GitHub de cada usuario (workflow, HyperFrames, Edge-TTS, FFmpeg, Docker/Render, Worker Cloudflare) |
| `web/` | App Android/PWA (`index.html`, `cloud_bundle.js`, `DroidScript_Main.js`, manifest, service worker) |
| `android/` | Proyecto Capacitor que convierte `web/` en APK |
| `windows/` | App Windows (`autodiag_studio_win.py`, `requirements.txt`, `build_exe.bat`) |
| `tools/` | `bundle.py` (regenera `web/cloud_bundle.js` tras editar `cloud/`) y un trabajo de prueba |
| `.github/workflows/build_apps.yml` | Compila el `.exe` y el `.apk` en GitHub Actions y hace un render de prueba |

## Uso (cualquier persona)
1. Instala el APK o abre el `.exe`.
2. ⚙️ Cuentas → pega tu llave de Gemini → **Probar Conexión**.
3. Crea tu token de GitHub con **Crear Token en 1 Clic** → pégalo → **🚀 Auto-Configurar mi Nube**.
4. 🎬 Estudio → escribe la idea → **Generar** → **Renderizar y Descargar MP4**.

## PWA en Cloudflare Pages
Sube la carpeta `web/` como proyecto de Cloudflare Pages (arrastrar y soltar). Desde Chrome en Android: menú → *Instalar app*.

## Compilar de nuevo
- EXE: en Windows, doble clic en `windows/build_exe.bat` (copia `cloud/` al lado).
- APK: `cd android && npm install && npx cap add android && npm run build:apk` (requiere Android SDK + JDK 21), o empuja a la rama `autodiag-studio-build` y GitHub Actions lo compila.
