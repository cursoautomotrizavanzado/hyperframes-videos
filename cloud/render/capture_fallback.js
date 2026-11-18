#!/usr/bin/env node
// Respaldo de captura si "npx hyperframes render" falla: Puppeteer + FFmpeg, cuadro a cuadro, determinista.
// Uso: node render/capture_fallback.js <proyecto/index.html> <salida_muda.mp4> [fps]
"use strict";
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

function findChrome() {
  const c = [process.env.CHROME_PATH, process.env.PUPPETEER_EXECUTABLE_PATH, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium", "/usr/bin/chromium-browser"].filter(Boolean);
  for (const p of c) if (fs.existsSync(p)) return p;
  throw new Error("No se encontró Chrome/Chromium (define CHROME_PATH)");
}

(async () => {
  const [html, out, fpsArg] = process.argv.slice(2);
  const fps = Number(fpsArg || 60);
  const browser = await puppeteer.launch({ executablePath: findChrome(), headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--allow-file-access-from-files", "--hide-scrollbars", "--force-color-profile=srgb"] });
  const page = await browser.newPage();
  await page.goto("file://" + path.resolve(html), { waitUntil: "load", timeout: 120000 });
  await page.waitForFunction("window.__render && window.__AD", { timeout: 60000 });
  const info = await page.evaluate(() => ({ d: window.__AD.duration, w: window.__AD.W, h: window.__AD.H }));
  await page.setViewport({ width: info.w, height: info.h, deviceScaleFactor: 1 });
  const total = Math.ceil(info.d * fps);
  console.log(`[capture] ${info.w}x${info.h} ${fps}fps ${total} cuadros`);
  const ff = spawn("ffmpeg", ["-y", "-v", "error", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", String(fps), out], { stdio: ["pipe", "inherit", "inherit"] });
  const t0 = Date.now();
  for (let i = 0; i < total; i++) {
    await page.evaluate((t) => window.__render(t), i / fps);
    const buf = await page.screenshot({ type: "jpeg", quality: 92, clip: { x: 0, y: 0, width: info.w, height: info.h }, optimizeForSpeed: true });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
    if (i % (fps * 2) === 0) console.log(`[capture] ${Math.round((i / total) * 100)}%  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  ff.stdin.end();
  await new Promise((r, j) => ff.on("close", (c) => (c === 0 ? r() : j(new Error("ffmpeg " + c)))));
  await browser.close();
  console.log("[capture] video mudo listo:", out);
})().catch((e) => { console.error(e); process.exit(1); });
