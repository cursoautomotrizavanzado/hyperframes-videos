// AutoDiag Video Studio — Proxy Cloudflare Worker (opcional)
// Guarda el token de GitHub en el servidor (no en el teléfono), resuelve CORS y entrega el MP4.
// Variables/secretos del Worker:
//   GITHUB_TOKEN  (secreto)  token con permisos repo + workflow
//   GITHUB_REPO   (texto)    "usuario/autodiag-hyperframes-engine"
//   APP_KEY       (secreto)  clave que la app envía en X-App-Key
//   BRANCH        (texto, opcional) rama principal, por defecto "main"
// API (igual que server/server.js):
//   POST /api/jobs {job, audio_b64?} -> {id}
//   GET  /api/jobs/:id               -> {state, step, log}
//   GET  /api/jobs/:id/video         -> video/mp4
//   DELETE /api/jobs/:id

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type, X-App-Key",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
};
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { ...CORS, "Content-Type": "application/json" } });

function b64utf8(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

function gh(env) {
  const repo = env.GITHUB_REPO;
  const branch = env.BRANCH || "main";
  const call = async (method, path, body, accept) => {
    const r = await fetch(`https://api.github.com${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: accept || "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AutoDiag-Worker",
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return r;
  };
  return {
    async putFile(path, contentB64, message) {
      let sha;
      const g = await call("GET", `/repos/${repo}/contents/${path}?ref=${branch}`);
      if (g.ok) sha = (await g.json()).sha;
      const r = await call("PUT", `/repos/${repo}/contents/${path}`, { message, content: contentB64, branch, sha });
      if (!r.ok) throw new Error(`PUT ${path}: ${r.status} ${await r.text()}`);
    },
    async dispatch(id) {
      const r = await call("POST", `/repos/${repo}/actions/workflows/render_video.yml/dispatches`, { ref: branch, inputs: { job_id: id } });
      if (!r.ok) throw new Error(`dispatch: ${r.status} ${await r.text()}`);
    },
    async findRun(id) {
      const r = await call("GET", `/repos/${repo}/actions/runs?event=workflow_dispatch&per_page=40`);
      if (!r.ok) return null;
      const d = await r.json();
      return (d.workflow_runs || []).find((x) => x.display_title === `render ${id}`) || null;
    },
    async currentStep(runId) {
      const r = await call("GET", `/repos/${repo}/actions/runs/${runId}/jobs`);
      if (!r.ok) return "";
      const d = await r.json();
      const steps = (d.jobs && d.jobs[0] && d.jobs[0].steps) || [];
      const s = steps.find((x) => x.status === "in_progress") || steps.filter((x) => x.status === "completed").pop();
      return s ? s.name : "";
    },
    raw(path, ref) { return call("GET", `/repos/${repo}/contents/${path}?ref=${encodeURIComponent(ref)}`, null, "application/vnd.github.raw"); },
    delBranch(ref) { return call("DELETE", `/repos/${repo}/git/refs/heads/${ref}`); },
  };
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    const url = new URL(req.url);
    if (url.pathname === "/" || url.pathname === "/health") return json({ ok: true, service: "autodiag-worker", repo: env.GITHUB_REPO });
    if (!env.APP_KEY || req.headers.get("X-App-Key") !== env.APP_KEY) return json({ error: "X-App-Key inválida" }, 401);
    const G = gh(env);
    const fm = url.pathname.match(/^\/api\/jobs\/([\w-]+)\/file\/([\w.-]+)$/);
    if (fm && req.method === "GET") {
      const r = await G.raw(fm[2], `render-${fm[1]}`);
      if (!r.ok) return json({ error: "Archivo no disponible" }, 404);
      return new Response(r.body, { headers: { ...CORS, "Content-Type": fm[2].endsWith(".png") ? "image/png" : "text/plain; charset=utf-8" } });
    }
    const m = url.pathname.match(/^\/api\/jobs(?:\/([\w-]+))?(\/video)?$/);
    if (!m) return json({ error: "Ruta no encontrada" }, 404);
    const id = m[1];
    try {
      if (req.method === "POST" && !id) {
        const body = await req.json();
        const job = body.job;
        if (!job || !Array.isArray(job.escenas)) return json({ error: "Falta job.escenas" }, 400);
        const jid = String(job.id || Date.now().toString(36)).replace(/[^\w-]/g, "");
        job.id = jid;
        if (body.audio_b64) await G.putFile(`jobs/${jid}.mp3`, body.audio_b64, `audio ${jid}`);
        await G.putFile(`jobs/${jid}.json`, b64utf8(JSON.stringify(job)), `job ${jid}`);
        await G.dispatch(jid);
        return json({ id: jid });
      }
      if (req.method === "GET" && id && m[2]) {
        const r = await G.raw("final.mp4", `render-${id}`);
        if (!r.ok) return json({ error: "Video no disponible" }, 404);
        return new Response(r.body, { headers: { ...CORS, "Content-Type": "video/mp4", "Content-Disposition": `attachment; filename="${id}.mp4"` } });
      }
      if (req.method === "GET" && id) {
        const run = await G.findRun(id);
        if (!run) return json({ id, state: "queued", step: "Esperando a GitHub Actions" });
        if (run.status !== "completed") return json({ id, state: "running", step: (await G.currentStep(run.id)) || run.status, run_url: run.html_url });
        const st = await G.raw("status.json", `render-${id}`);
        if (st.ok) { const s = await st.json(); return json({ id, state: s.state, step: s.state === "ok" ? "Completado" : "Error", log: s.log, files: s.files || [], run_url: run.html_url }); }
        return json({ id, state: run.conclusion === "success" ? "running" : "error", step: run.conclusion, run_url: run.html_url });
      }
      if (req.method === "DELETE" && id) {
        await G.delBranch(`render-${id}`);
        return json({ ok: true });
      }
      return json({ error: "Método no permitido" }, 405);
    } catch (e) {
      return json({ error: String(e.message || e) }, 500);
    }
  },
};
