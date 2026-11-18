#!/usr/bin/env node
// Alternativa a GitHub Actions: servidor de render para Render.com (Docker) o cualquier VPS.
// API compatible con worker.js:
//   POST   /api/jobs            {job, audio_b64?}  -> {id}
//   GET    /api/jobs/:id        -> {state: queued|running|ok|error, step, log}
//   GET    /api/jobs/:id/video  -> video/mp4
//   DELETE /api/jobs/:id
// Seguridad: encabezado X-App-Key debe coincidir con la variable APP_KEY.
"use strict";
const express = require("express");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");

const APP_KEY = process.env.APP_KEY || "";
const ROOT = path.resolve(__dirname, "..");
const WORK = process.env.WORK_DIR || path.join(os.tmpdir(), "autodiag-jobs");
fs.mkdirSync(WORK, { recursive: true });

const jobs = new Map(); // id -> {state, step, log, dir}
const queue = [];
let busy = false;

const app = express();
app.use(express.json({ limit: "60mb" }));
app.use((req, res, next) => {
  res.set("Access-Control-Allow-Origin", "*");
  res.set("Access-Control-Allow-Headers", "Content-Type, X-App-Key");
  res.set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  if (req.path === "/" || req.path === "/health") return next();
  if (!APP_KEY || req.get("X-App-Key") !== APP_KEY) return res.status(401).json({ error: "X-App-Key inválida" });
  next();
});

app.get(["/", "/health"], (_req, res) => res.json({ ok: true, service: "autodiag-render", queue: queue.length, busy }));

app.post("/api/jobs", (req, res) => {
  const job = req.body && req.body.job;
  if (!job || !Array.isArray(job.escenas)) return res.status(400).json({ error: "Falta job.escenas" });
  const id = String(job.id || crypto.randomBytes(6).toString("hex")).replace(/[^\w-]/g, "");
  const dir = path.join(WORK, id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "job.json"), JSON.stringify(job));
  if (req.body.audio_b64) fs.writeFileSync(path.join(dir, "audio.mp3"), Buffer.from(req.body.audio_b64, "base64"));
  jobs.set(id, { state: "queued", step: "En cola", log: "", dir });
  queue.push(id);
  pump();
  res.json({ id });
});

app.get("/api/jobs/:id", (req, res) => {
  const j = jobs.get(req.params.id);
  if (!j) return res.status(404).json({ error: "No existe" });
  res.json({ id: req.params.id, state: j.state, step: j.step, log: j.log.slice(-4000) });
});

app.get("/api/jobs/:id/video", (req, res) => {
  const j = jobs.get(req.params.id);
  const f = j && path.join(j.dir, "out", "final.mp4");
  if (!f || !fs.existsSync(f)) return res.status(404).json({ error: "Video no disponible" });
  res.set("Content-Type", "video/mp4");
  res.set("Content-Disposition", `attachment; filename="${req.params.id}.mp4"`);
  fs.createReadStream(f).pipe(res);
});

app.delete("/api/jobs/:id", (req, res) => {
  const j = jobs.get(req.params.id);
  if (j) fs.rmSync(j.dir, { recursive: true, force: true });
  jobs.delete(req.params.id);
  res.json({ ok: true });
});

function pump() {
  if (busy || !queue.length) return;
  busy = true;
  const id = queue.shift();
  const j = jobs.get(id);
  j.state = "running"; j.step = "Iniciando";
  const audio = path.join(j.dir, "audio.mp3");
  const args = [path.join(ROOT, "render", "pipeline.sh"), path.join(j.dir, "job.json"), path.join(j.dir, "out")];
  if (fs.existsSync(audio)) args.push(audio);
  const p = spawn("bash", args, { cwd: ROOT, env: process.env });
  const onData = (d) => {
    const s = d.toString();
    j.log += s;
    const m = s.match(/::group::(.+)/);
    if (m) j.step = m[1].trim();
    const pct = s.match(/(\d+)%/);
    if (pct && /capture|█/.test(s)) j.step = j.step.replace(/ \(\d+%\)$/, "") + ` (${pct[1]}%)`;
  };
  p.stdout.on("data", onData);
  p.stderr.on("data", onData);
  p.on("close", (code) => {
    j.state = code === 0 && fs.existsSync(path.join(j.dir, "out", "final.mp4")) ? "ok" : "error";
    j.step = j.state === "ok" ? "Completado" : "Error";
    busy = false;
    pump();
  });
}

// Limpieza: borra trabajos con más de 6 horas
setInterval(() => {
  const limit = Date.now() - 6 * 3600e3;
  for (const [id, j] of jobs) {
    try { if (fs.statSync(j.dir).mtimeMs < limit && j.state !== "running") { fs.rmSync(j.dir, { recursive: true, force: true }); jobs.delete(id); } } catch (e) { jobs.delete(id); }
  }
}, 30 * 60e3);

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log(`[server] AutoDiag Render escuchando en :${PORT}`));
