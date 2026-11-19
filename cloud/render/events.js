#!/usr/bin/env node
// Lee de la composición los eventos de sonido (pastillas, cambios de escena, alertas, cierre).
// Uso: node render/events.js <proyecto/index.html> <salida/events.json>
"use strict";
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");
const c = [process.env.CHROME_PATH, process.env.PUPPETEER_EXECUTABLE_PATH, "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"].filter(Boolean).find((p) => fs.existsSync(p));
(async () => {
  const [html, out] = process.argv.slice(2);
  const b = await puppeteer.launch({ executablePath: c, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--allow-file-access-from-files"] });
  const p = await b.newPage();
  await p.goto("file://" + path.resolve(html), { waitUntil: "load", timeout: 60000 });
  await p.waitForFunction("window.__AD", { timeout: 30000 });
  const d = await p.evaluate(() => ({ duration: window.__AD.duration, sonido: window.__AD.sonido, events: window.__AD.events || [] }));
  await b.close();
  fs.writeFileSync(out, JSON.stringify(d, null, 1));
  console.log(`[sfx] ${d.events.length} eventos de sonido`);
})().catch((e) => { console.error("[sfx] sin eventos:", e.message); process.exit(0); });
