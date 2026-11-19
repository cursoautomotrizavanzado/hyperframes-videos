#!/usr/bin/env node
// Exporta un carrusel (job.salida = "carrusel") como imágenes PNG 1080x1350 + copy.txt
// Uso: node render/slides.js <proyecto/index.html> <job.json> <carpeta_salida>
"use strict";
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");
const chrome = [process.env.CHROME_PATH, process.env.PUPPETEER_EXECUTABLE_PATH, "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"].filter(Boolean).find((p) => fs.existsSync(p));
function copyText(job) {
  const c = job.copy || {}, out = [];
  for (const red of ["instagram", "facebook", "tiktok"]) {
    if (!c[red]) continue;
    out.push(`=== ${red.toUpperCase()} ===`, c[red].gancho || "", "", c[red].descripcion || "", "", c[red].hashtags || "", "");
  }
  return out.join("\n");
}
(async () => {
  const [html, jobPath, out] = process.argv.slice(2);
  const job = JSON.parse(fs.readFileSync(jobPath, "utf8"));
  const b = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--allow-file-access-from-files"] });
  const p = await b.newPage();
  await p.goto("file://" + path.resolve(html), { waitUntil: "load", timeout: 60000 });
  await p.waitForFunction("window.__render && window.__AD", { timeout: 30000 });
  await p.evaluate(() => document.fonts && document.fonts.ready);
  const info = await p.evaluate(() => ({ w: window.__AD.W, h: window.__AD.H, n: window.__AD.timeline.scenes.length }));
  await p.setViewport({ width: info.w, height: info.h, deviceScaleFactor: 1 });
  const files = [];
  for (let i = 0; i < info.n; i++) {
    await p.evaluate((t) => window.__render(t), i * 2 + 1.9);
    const f = `carrusel_${String(i + 1).padStart(2, "0")}.png`;
    await p.screenshot({ path: path.join(out, f), type: "png", clip: { x: 0, y: 0, width: info.w, height: info.h } });
    files.push(f);
  }
  await b.close();
  const ct = copyText(job);
  if (ct.trim()) { fs.writeFileSync(path.join(out, "copy.txt"), ct); files.push("copy.txt"); }
  fs.writeFileSync(path.join(out, "files.json"), JSON.stringify(files));
  console.log(`[carrusel] ${info.n} imágenes listas`);
})().catch((e) => { console.error(e); process.exit(1); });
