#!/usr/bin/env node
// Construye la composición HyperFrames (index.html) a partir del job + timeline real.
// Uso: node render/build_composition.js <job.json> <timeline.json> <carpeta_salida>
"use strict";
const fs = require("fs");
const path = require("path");

function safeJson(obj) {
  return JSON.stringify(obj).replace(/</g, "\\u003c").replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
}

function buildHtml(template, job, timeline, opts) {
  opts = opts || {};
  const wide = job.formato === "16:9";
  const W = wide ? 1920 : 1080, H = wide ? 1080 : 1920;
  const duration = timeline && timeline.duration ? Number(timeline.duration).toFixed(3) : "10";
  const libre = String(job.codigo_libre || "").replace(/<\/script/gi, "<\\/script");
  return template
    .split("__W__").join(String(W))
    .split("__H__").join(String(H))
    .split("__DURATION__").join(duration)
    .split("__FPS__").join(String(job.fps || 60))
    .replace("/*__JOB__*/null", safeJson(job))
    .replace("/*__TIMELINE__*/null", timeline ? safeJson(timeline) : "null")
    .replace("/*__PREVIEW__*/false", opts.preview ? "true" : "false")
    .replace("/*__LIBRE__*/", libre);
}

module.exports = { buildHtml };

if (require.main === module) {
  const [jobPath, tlPath, outDir] = process.argv.slice(2);
  if (!jobPath || !tlPath || !outDir) {
    console.error("Uso: build_composition.js job.json timeline.json outDir");
    process.exit(2);
  }
  const job = JSON.parse(fs.readFileSync(jobPath, "utf8"));
  const tl = JSON.parse(fs.readFileSync(tlPath, "utf8"));
  const tpl = fs.readFileSync(path.join(__dirname, "engine.html"), "utf8");
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "index.html"), buildHtml(tpl, job, tl));
  // GSAP local (sin depender de CDN durante el render)
  try { fs.copyFileSync(require.resolve("gsap/dist/gsap.min.js"), path.join(outDir, "gsap.min.js")); }
  catch (e) { console.warn("[build] gsap no instalado localmente:", e.message); }
  // Fuente Poppins local (estilo Pastillas)
  try {
    const fdir = path.join(path.dirname(require.resolve("@fontsource/poppins/package.json")), "files");
    fs.mkdirSync(path.join(outDir, "fonts"), { recursive: true });
    for (const w of [500, 600, 700, 800]) fs.copyFileSync(path.join(fdir, `poppins-latin-${w}-normal.woff2`), path.join(outDir, "fonts", `poppins-latin-${w}-normal.woff2`));
  } catch (e) { console.warn("[build] Poppins no disponible:", e.message); }
  console.log(`[build] composición lista: ${path.join(outDir, "index.html")} (${tl.duration}s, ${job.formato})`);
}
