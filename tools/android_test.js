// Prueba automática del APK en el emulador: toca pestañas y botones reales y guarda capturas + errores.
// Uso (dentro del emulador de CI): node tools/android_test.js <carpeta_salida>
"use strict";
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const OUT = process.argv[2] || "android_test";
fs.mkdirSync(OUT, { recursive: true });
const PKG = "com.autodiag.videostudio";
const sh = (c) => { try { return execSync(c, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim(); } catch (e) { return "ERR " + (e.stderr || e.message); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = [];
const rec = (k, v) => { const line = `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`; console.log(line); log.push(line); };
let shot = 0;
function cap(name) { const f = path.join(OUT, `${String(++shot).padStart(2, "0")}_${name}.png`); sh(`adb exec-out screencap -p > "${f}"`); }

(async () => {
  let pid = "";
  for (let i = 0; i < 30 && !pid; i++) { pid = sh(`adb shell pidof ${PKG}`); if (!pid || pid.startsWith("ERR")) { pid = ""; await sleep(2000); } }
  rec("pid", pid);
  const socks = sh("adb shell cat /proc/net/unix | grep webview_devtools_remote");
  rec("sockets", socks);
  const m = socks.match(/@?(webview_devtools_remote_\d+)/);
  if (!m) { cap("sin_devtools"); fs.writeFileSync(path.join(OUT, "results.txt"), log.join("\n")); process.exit(0); }
  sh(`adb forward tcp:9222 localabstract:${m[1]}`);
  await sleep(1500);
  const browser = await puppeteer.connect({ browserURL: "http://127.0.0.1:9222", defaultViewport: null });
  const pages = await browser.pages();
  const page = pages.find((p) => /localhost/.test(p.url())) || pages[0];
  rec("url", page.url());
  page.on("console", (msg) => rec("console." + msg.type(), msg.text()));
  page.on("pageerror", (e) => rec("PAGEERROR", e.message));
  await page.reload({ waitUntil: "load" });
  await sleep(3000);
  rec("env", await page.evaluate(() => ({ w: innerWidth, h: innerHeight, dpr: devicePixelRatio, cap: !!window.Capacitor, plugins: window.Capacitor ? Object.keys(Capacitor.Plugins || {}) : [], ua: navigator.userAgent })));
  cap("inicio");
  sh("adb shell uiautomator dump /sdcard/u.xml");
  const ux = sh("adb shell cat /sdcard/u.xml");
  const wb = ux.match(/class="android\.webkit\.WebView"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/) || ux.match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*class="android\.webkit\.WebView"/);
  const WV = wb ? { x: +wb[1], y: +wb[2], w: +wb[3] - +wb[1], h: +wb[4] - +wb[2] } : { x: 0, y: 0 };
  rec("webview_bounds", WV);

  // ¿Qué elemento recibe el toque en el centro de cada botón visible? (detecta capas que tapan botones)
  async function probe(sel) {
    return page.evaluate((sel) => {
      const el = document.querySelector(sel); if (!el) return { sel, existe: false };
      el.scrollIntoView({ block: "center" });
      const r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2, top = document.elementFromPoint(x, y);
      return { sel, x: Math.round(x), y: Math.round(y), w: Math.round(r.width), h: Math.round(r.height), recibe: top ? (top === el || el.contains(top)) : false, encima: top ? (top.id || top.className || top.tagName) : null };
    }, sel);
  }
  async function tap(sel, name) {
    const p = await probe(sel); rec("probe " + name, p);
    if (!p.existe && p.existe !== undefined) return p;
    await sleep(400);
    // toque real a nivel de Android (coordenadas físicas dentro del WebView)
    const dpr = await page.evaluate(() => devicePixelRatio);
    const X = Math.round(WV.x + p.x * dpr), Y = Math.round(WV.y + p.y * dpr), webTop = WV.y;
    rec("tap " + name, { X, Y, webTop });
    sh(`adb shell input tap ${X} ${Y}`);
    await sleep(1500);
    cap(name);
    rec("toast " + name, await page.evaluate(() => { const t = document.getElementById("toast"); return t && t.style.display !== "none" ? t.textContent : ""; }));
    return p;
  }
  const tabState = () => page.evaluate(() => [...document.querySelectorAll(".view")].map((v) => v.id + ":" + v.classList.contains("act")).join(" "));

  await tap('[data-tab="accounts"]', "tab_cuentas"); rec("vistas", await tabState());
  await tap('[data-tab="studio"]', "tab_estudio"); rec("vistas", await tabState());
  await tap('[data-tab="accounts"]', "tab_cuentas_2"); rec("vistas", await tabState());
  for (const [sel, n] of [["#btnGTest", "probar_gemini_vacio"], ["#btnGhTest", "probar_github_vacio"], ["#btnProvision", "autoconfigurar_vacio"], ["#btnProfNew", "perfil_nuevo_vacio"], ["#btnRenderDeploy", "render_deploy"], ["#btnCopyWorker", "copiar_worker"]]) await tap(sel, n);
  await page.evaluate(() => { const e = document.getElementById("gKey"); e.value = "AIzaInvalida123"; e.dispatchEvent(new Event("change")); });
  await tap("#btnGTest", "probar_gemini_invalida"); await sleep(4000); rec("gStatus", await page.evaluate(() => document.getElementById("gStatus").textContent));
  await page.evaluate(() => { const e = document.getElementById("ghToken"); e.value = "ghp_invalido123"; e.dispatchEvent(new Event("change")); });
  await tap("#btnGhTest", "probar_github_invalido"); await sleep(4000); rec("ghStatus", await page.evaluate(() => document.getElementById("ghStatus").textContent));
  await tap("#btnProvision", "autoconfigurar_invalido"); await sleep(4000); rec("provLog", await page.evaluate(() => document.getElementById("provLog").textContent));
  await tap("#btnGKeyGet", "obtener_api_key"); await sleep(2500); cap("tras_obtener_key"); sh("adb shell input keyevent KEYCODE_BACK"); await sleep(2000);
  await tap('[data-tab="studio"]', "tab_estudio_2");
  for (const [sel, n] of [["#btnGen", "generar_vacio"], ["#btnPromptCopy", "prompt_vacio"], ["#btnCopyGuion", "copiar_guion"], ["#btnSpeak", "voz_prueba"], ["#btnHtml", "html"], ["#btnRender", "render_sin_datos"]]) await tap(sel, n);
  await page.evaluate(() => { document.getElementById("guion").value = "El sensor CKP inductivo genera una señal alterna. El hueco marca la referencia."; });
  await tap("#btnPromptCopy", "prompt_con_guion");
  await page.evaluate(() => { document.querySelector("details").open = true; document.getElementById("scenesJson").value = '```json\n{"titulo":"Prueba","escenas":[{"tipo":"osciloscopio","texto":"El sensor CKP inductivo genera una señal alterna.","datos":{"senal":"ckp_inductivo","rpm":800,"resaltar":"diente_faltante"}}]}\n```'; });
  await tap("#btnApplyJson", "aplicar_escenas"); await sleep(2500); cap("vista_previa");
  rec("pvInfo", await page.evaluate(() => document.getElementById("pvInfo").textContent));
  fs.writeFileSync(path.join(OUT, "results.txt"), log.join("\n"));
  browser.disconnect();
})().catch((e) => { rec("FATAL", String(e && e.stack || e)); fs.writeFileSync(path.join(OUT, "results.txt"), log.join("\n")); process.exit(0); });
