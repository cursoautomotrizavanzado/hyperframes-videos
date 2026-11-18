# AutoDiag Video Studio - servidor de render (Render.com / VPS)
FROM node:22-bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive \
    CHROME_PATH=/usr/bin/chromium \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    PUPPETEER_SKIP_DOWNLOAD=1 \
    WHISPER_MODEL=base
RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium ffmpeg python3 python3-pip ca-certificates \
      fonts-noto-core fonts-noto-color-emoji fonts-dejavu-core fonts-jetbrains-mono \
    && pip3 install --no-cache-dir --break-system-packages edge-tts faster-whisper \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund
COPY render ./render
COPY server ./server
EXPOSE 10000
CMD ["node", "server/server.js"]
