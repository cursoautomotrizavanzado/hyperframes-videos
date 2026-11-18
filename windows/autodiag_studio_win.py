# -*- coding: utf-8 -*-
"""
AutoDiag Video Studio (Multi-User Edition) — Versión Windows
Interfaz customtkinter · Gemini · Auto-aprovisionamiento GitHub/Cloudflare/Render · Lote desde Excel
"""
import base64
import csv
import ctypes
import json
import os
import re
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime

import requests
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

APP_NAME = "AutoDiag Video Studio"
VERSION = "1.0.0"

# ----------------------------------------------------------------- rutas
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RES_DIR = BASE_DIR
CLOUD_DIR = next((p for p in [os.path.join(RES_DIR, "cloud"), os.path.join(BASE_DIR, "cloud"),
                              os.path.join(BASE_DIR, "..", "cloud")] if os.path.isdir(p)), os.path.join(RES_DIR, "cloud"))
CONFIG_FILE = os.path.join(BASE_DIR, "config_profiles.json")
VIDEOS_DIR = os.path.join(BASE_DIR, "Videos_Listos")

C = {"bg": "#080D16", "panel": "#172132", "panel2": "#0F1828", "border": "#2A3B54", "orange": "#F76015",
     "cyan": "#00E5FF", "red": "#FF3B30", "green": "#34C759", "yellow": "#FFD60A", "text": "#E8EEF7", "dim": "#7F92AE"}

VOICES = {"Jorge · México (masculina)": "es-MX-JorgeNeural", "Sebastián · Venezuela (masculina)": "es-VE-SebastianNeural",
          "Gonzalo · Colombia (masculina)": "es-CO-GonzaloNeural", "Alonso · EE.UU. (masculina)": "es-US-AlonsoNeural",
          "Álvaro · España (masculina)": "es-ES-AlvaroNeural", "Dalia · México (femenina)": "es-MX-DaliaNeural"}
TEMPLATES = {"Automática (la IA elige)": "auto", "Osciloscopio CKP / CMP": "osciloscopio", "PWM / Inyectores": "pwm",
             "Relés ISO / Flujo 12V-24V": "rele", "Pinout ECU": "pinout", "Libre (la IA programa la simulación)": "libre"}
ESTILOS = {"Osciloscopio Pro (oscuro)": "osciloscopio", "Blueprint técnico (azul)": "blueprint", "Carbono (negro mate)": "carbono",
           "Neón (morado)": "neon", "Taller claro (fondo blanco)": "claro", "Pastillas azul (sin subtítulos)": "pastillas"}
RATES = {"Pausada": "-5%", "Normal": "+0%", "Ágil (reels)": "+8%", "Rápida": "+15%"}


# ----------------------------------------------------------------- cifrado DPAPI (Windows) para config_profiles.json
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    if os.name != "nt":
        return data
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    inp, out = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), _Blob()
    fn = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0x01, ctypes.byref(out)):
        raise OSError("DPAPI falló")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


SECRET_KEYS = ("geminiKey", "githubToken", "proxyKey", "cfToken")


def load_store():
    store = {"active": "Perfil principal", "profiles": {"Perfil principal": {}}}
    if os.path.exists(CONFIG_FILE):
        try:
            store = json.load(open(CONFIG_FILE, encoding="utf-8"))
            for p in store.get("profiles", {}).values():
                for k in SECRET_KEYS:
                    v = p.get(k)
                    if isinstance(v, str) and v.startswith("enc:"):
                        try:
                            p[k] = _dpapi(base64.b64decode(v[4:]), False).decode("utf-8")
                        except Exception:
                            p[k] = ""
        except Exception:
            pass
    return store


def save_store(store):
    data = json.loads(json.dumps(store))
    for p in data.get("profiles", {}).values():
        for k in SECRET_KEYS:
            if p.get(k):
                try:
                    p[k] = "enc:" + base64.b64encode(_dpapi(p[k].encode("utf-8"), True)).decode()
                except Exception:
                    pass
    tmp = CONFIG_FILE + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)


# ----------------------------------------------------------------- archivos del motor (cloud/)
def cloud_files():
    files = {}
    for base, dirs, names in os.walk(CLOUD_DIR):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "out")]
        for n in names:
            p = os.path.join(base, n)
            files[os.path.relpath(p, CLOUD_DIR).replace(os.sep, "/")] = open(p, encoding="utf-8").read()
    return files


def engine_template():
    return open(os.path.join(CLOUD_DIR, "render", "engine.html"), encoding="utf-8").read()


def safe_json(o):
    return json.dumps(o, ensure_ascii=False).replace("<", "\\u003c")


def build_html(job, timeline, preview=False):
    wide = job.get("formato") == "16:9"
    W, H = (1920, 1080) if wide else (1080, 1920)
    dur = "%.3f" % timeline["duration"] if timeline else "10"
    html = engine_template()
    for a, b in (("__W__", str(W)), ("__H__", str(H)), ("__DURATION__", dur), ("__FPS__", str(job.get("fps", 60)))):
        html = html.replace(a, b)
    html = html.replace("/*__JOB__*/null", safe_json(job)).replace("/*__TIMELINE__*/null", safe_json(timeline) if timeline else "null")
    html = html.replace("/*__PREVIEW__*/false", "true" if preview else "false")
    if preview:
        html = html.replace('<script src="gsap.min.js"></script>', "")
    html = html.replace("/*__LIBRE__*/", re.sub(r"</script", r"<\\/script", job.get("codigo_libre", "") or "", flags=re.I))
    return html


def estimate_timeline(job):
    toks = []
    for i, s in enumerate(job["escenas"]):
        for w in (s.get("texto") or "").split():
            toks.append((w, i))
    rate = {"-5%": 2.3, "+0%": 2.45, "+8%": 2.65, "+15%": 2.85}.get(job.get("velocidad"), 2.55)
    dur = max(4.0, len(toks) / rate + 1.1)
    weights = [len(re.sub(r"[^\wáéíóúüñÁÉÍÓÚÜÑ]", "", w)) + 2 + (3.5 if re.search(r"[.,;:!?…]$", w) else 0) for w, _ in toks]
    total = sum(weights) or 1
    t, usable, words = 0.35, dur - 0.85, []
    for (w, i), k in zip(toks, weights):
        d = usable * k / total
        words.append({"word": w, "start": round(t, 3), "end": round(t + d * 0.88, 3), "seg": i})
        t += d
    return {"duration": round(dur, 3), "language": "es", "words": words, "source": "estimado"}


# ----------------------------------------------------------------- Gemini
TPL_HELP = {
    "osciloscopio": 'datos: {"senal":"ckp_inductivo|ckp_hall|cmp_hall|ckp_cmp","rpm":800,"dientes":60,"faltantes":2,"vpp":4,"resaltar":"diente_faltante|null","falla":"null|ruido|diente_danado|sin_senal"}',
    "pwm": 'datos: {"senal":"pwm|inyector","voltaje":13.8,"frecuencia_hz":100,"duty":40,"ancho_ms":3,"pico_inductivo_v":62,"corriente_a":1,"falla":"null|sin_pico|circuito_abierto"}',
    "rele": 'datos: {"voltaje":12|24,"activacion_en":1.2,"carga":"bomba|ventilador|bocina","control":"ECU (masa al 85)","falla":"null|bobina_abierta|contacto_quemado"}',
    "pinout": 'datos: {"conector":"ECU A","filas":3,"columnas":8,"pines":[{"n":1,"etiqueta":"+12V IGN","tipo":"alimentacion|masa|senal|can|control|pwm","valor":"12.6 V"}],"resaltar":[1]}',
    "concepto": 'datos: {"puntos":["etiqueta corta 1","etiqueta corta 2","etiqueta corta 3"]}  (máx 5, 2-5 palabras cada una)',
}


PAST_TXT = 'ESTILO PASTILLAS (obligatorio en este video): cada escena DEBE incluir además "pastillas": 1 a 3 objetos {"texto":"idea clave dicha en esa escena, máx 40 caracteres","color":"verde|blanco|cian|rojo|ambar|azul"} y "resumen": frase corta de máx 32 caracteres que resume la escena. "titulo" máx 32 caracteres. La ÚLTIMA escena es de tipo "cierre" (su "titulo" es la conclusión en una frase).\nTipos de escena disponibles en este estilo (elige el que ilustre literalmente lo narrado):\n- inyector_retorno → datos: {"riel":true|false,"deposito":true|false,"flujo":"normal|exceso","etiquetas_laterales":[{"texto":"HOLGURAS INTERNAS","color":"verde"}],"manometro":{"valor":0.25,"etiqueta":"PRESIÓN DEL RIEL","alerta":"¡SE DESPERDICIA!"},"retorno_texto":"RETORNO"}\n- manometro → datos: {"valor":0.0-1.0,"etiqueta":"PRESIÓN DEL RIEL","alerta":"texto opcional"}\n- probetas → datos: {"multiplicador":"× 8","items":[{"etiqueta":"INYECTOR 1","valor":"3 cm³","nivel":0.1,"alerta":false}]} (1 a 6 probetas; nivel 0-1 proporcional al valor)\n- lista → datos: {"encabezado":"SI TODOS ESTÁN ALTOS, REVISA:","items":[{"titulo":"PRESIÓN DEL RIEL","detalle":"NO MAYOR A LA PEDIDA"}]} (máx 4)\n- manual → datos: {"titulo":"MANUAL DEL FABRICANTE","nota":"texto corto opcional"}\n- lupa → datos: {"etiqueta":"UNIÓN","detalle":"texto corto opcional"}\n- lineas → datos: {"lineas":[{"etiqueta":"RIEL - ALTA PRESIÓN","tipo":"alta"},{"etiqueta":"RETORNO - BAJA PRESIÓN","tipo":"baja"}]}\n- tarjeta → datos: {"color":"verde","lineas":[{"texto":"PRIMERO","color":"blanco"},{"texto":"CONECTA LAS MANGUERAS","color":"blanco"},{"texto":"ANTES DE ARRANCAR","color":"verde"}]}\n- osciloscopio, pwm, rele, pinout → mismos datos de arriba\n- cierre → datos: {}'


def build_prompt(idea, tpl, exact, formato, estilo="osciloscopio"):
    if tpl == "auto":
        tipos = "Elige para cada escena el tipo que mejor ilustre literalmente lo narrado: concepto, osciloscopio, pwm, rele, pinout."
    elif tpl == "libre":
        tipos = 'Usa el tipo "libre" en las escenas técnicas (y "concepto" donde convenga).'
    else:
        tipos = f'La plantilla principal es "{tpl}": úsala en la mayoría de escenas técnicas; puedes usar "concepto" en introducción y cierre.'
    tarea = ("toma EXACTAMENTE este guion (no cambies ni una palabra) y divídelo en escenas" if exact else
             "escribe un guion de voz de 60 a 90 segundos (150-220 palabras), técnico, preciso y natural para locución, con un gancho en la primera frase y un cierre útil")
    libre = ""
    if tpl == "libre":
        libre = ('- libre → "codigo_libre": código JavaScript que define window.renderLibre = function(ctx, info){...}. info = {t, local, dur, scene, rect:{x,y,w,h}, C, W, H, MONO, SANS}. '
                 "Dibuja con Canvas 2D DENTRO de rect, en función SOLO del tiempo (determinista: nada de Math.random, Date ni requestAnimationFrame). "
                 "Usa info.scene.datos e info.local (segundos dentro de la escena). Colores: C.orange #F76015, C.cyan #00E5FF, C.red #FF3B30 (+12V), C.green #34C759 (masa), C.yellow #FFD60A (control/PWM). "
                 "Simulación física/eléctrica real y animada, no diapositivas.\n")
    return f"""Eres un instructor experto en diagnóstico automotriz (electrónica, osciloscopio, sensores, actuadores, redes CAN) y guionista de videos cortos técnicos en español latinoamericano.
Tarea: {tarea} sobre:
\"\"\"{idea}\"\"\"
Formato del video: {"16:9 (curso en PC)" if formato == "16:9" else "9:16 (TikTok/Reels)"}.
{tipos}
Reglas:
- Precisión técnica primero: valores reales y típicos (voltajes, Vpp, resistencias, frecuencias). Nada inventado ni dudoso.
- El texto en pantalla son etiquetas cortas; la explicación la lleva la voz.
- Los campos "texto" de las escenas, concatenados con un espacio, deben ser idénticos a "guion_voz". 4 a 8 escenas.
- La primera escena es el gancho. Números escritos como se pronuncian en "texto" (ej. "cinco voltios"), pero en badges usa cifras ("5 V").
- badges: 1 a 4 por escena, con magnitudes, pines, voltajes o fallas mencionadas. tipo ∈ voltaje|masa|senal|corriente|control|pwm|can|falla|temperatura|resistencia|tiempo|rpm.
Esquemas de "datos" por tipo:
- osciloscopio → {TPL_HELP['osciloscopio']}
- pwm → {TPL_HELP['pwm']}
- rele → {TPL_HELP['rele']}
- pinout → {TPL_HELP['pinout']}
- concepto → {TPL_HELP['concepto']}
{(PAST_TXT + chr(10)) if estilo == "pastillas" else ""}{libre}Responde SOLO JSON válido con esta forma:
{{"titulo":"gancho de portada (máx 55 caracteres)","subtitulo":"frase corta","guion_voz":"...","escenas":[{{"tipo":"...","titulo":"máx 38 caracteres","etiqueta":"MAYÚSCULAS CORTA","texto":"fragmento del guion","badges":[{{"etiqueta":"Vpp","valor":"4.2 V","tipo":"senal"}}],"datos":{{}}{',"pastillas":[{"texto":"...","color":"verde"}],"resumen":"..."' if estilo == "pastillas" else ""}}}]{',"codigo_libre":"..."' if tpl == "libre" else ""}}}"""


def gemini_models(key):
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200}, timeout=30)
    d = r.json()
    if not r.ok:
        raise RuntimeError(d.get("error", {}).get("message", r.status_code))
    ms = [m["name"].replace("models/", "") for m in d.get("models", [])
          if "generateContent" in m.get("supportedGenerationMethods", []) and "gemini" in m["name"]]
    ms = [m for m in ms if not re.search(r"embedding|tts|image|audio|live|vision", m)]
    return sorted(ms, reverse=True)


def gemini_generate(key, model, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.6, "maxOutputTokens": 16384}}
    for attempt in range(3):
        r = requests.post(url, params={"key": key}, json=body, timeout=180)
        if r.status_code in (429, 500, 503) and attempt < 2:
            time.sleep(6 * (attempt + 1))
            continue
        d = r.json()
        if not r.ok:
            raise RuntimeError(d.get("error", {}).get("message", r.status_code))
        txt = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        m = re.search(r"\{[\s\S]*\}", txt)
        if not m:
            raise RuntimeError("Gemini no devolvió JSON")
        return json.loads(m.group(0))


def parse_scenes_text(txt):
    """Acepta el JSON tal como lo entrega Gemini/Claude: con ```json, texto alrededor o solo la lista de escenas."""
    txt = (txt or "").strip()
    if not txt:
        return {}
    txt = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", txt.strip())
    starts = [i for i in (txt.find("{"), txt.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no encontré un JSON")
    i = min(starts)
    end = max(txt.rfind("}"), txt.rfind("]"))
    obj = json.loads(txt[i:end + 1])
    if isinstance(obj, list):
        obj = {"escenas": obj}
    return obj


def normalize(d, fallback=""):
    tipos = ("concepto", "osciloscopio", "pwm", "rele", "pinout", "libre", "inyector_retorno", "manometro", "probetas", "lista",
             "manual", "lupa", "lineas", "tarjeta", "cierre")
    d["escenas"] = [s for s in d.get("escenas", []) if s and s.get("texto")]
    if not d["escenas"]:
        d["escenas"] = [{"tipo": "concepto", "titulo": d.get("titulo", ""), "texto": d.get("guion_voz") or fallback}]
    for s in d["escenas"]:
        s["tipo"] = s.get("tipo") if s.get("tipo") in tipos else "concepto"
        s["datos"] = s.get("datos") or {}
        s["badges"] = (s.get("badges") or [])[:4]
    d["guion_voz"] = " ".join(s["texto"].strip() for s in d["escenas"])
    return d


# ----------------------------------------------------------------- GitHub
class GitHub:
    def __init__(self, token):
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "AutoDiag-Studio"})

    def req(self, method, path, ok=True, **kw):
        r = self.s.request(method, "https://api.github.com" + path, timeout=120, **kw)
        if ok and not r.ok:
            try:
                msg = r.json().get("message")
            except Exception:
                msg = r.text[:200]
            raise RuntimeError(f"GitHub {method} {path}: {r.status_code} {msg}")
        return r

    def put_file(self, repo, path, content_bytes, branch, message):
        sha = None
        g = self.req("GET", f"/repos/{repo}/contents/{path}", ok=False, params={"ref": branch})
        if g.ok:
            sha = g.json().get("sha")
        body = {"message": message, "content": base64.b64encode(content_bytes).decode(), "branch": branch}
        if sha:
            body["sha"] = sha
        for a in range(3):
            try:
                return self.req("PUT", f"/repos/{repo}/contents/{path}", json=body)
            except RuntimeError:
                if a == 2:
                    raise
                time.sleep(1.5)


def provision_github(token, repo_name, private, log):
    gh = GitHub(token)
    log("1/5 · Verificando usuario…")
    user = gh.req("GET", "/user").json()["login"]
    log(f"   ✔ Hola, {user}")
    log(f"2/5 · Buscando repositorio {repo_name}…")
    r = gh.req("GET", f"/repos/{user}/{repo_name}", ok=False)
    if r.ok:
        info = r.json()
        log("   ✔ Ya existe, se actualizará")
    else:
        info = gh.req("POST", "/user/repos", json={"name": repo_name, "private": private, "auto_init": True,
                                                    "description": "Motor de render de AutoDiag Video Studio (HyperFrames + Edge-TTS + FFmpeg)"}).json()
        log(f"   ✔ Repositorio creado ({'privado' if private else 'público'})")
        time.sleep(2.5)
    branch = info.get("default_branch", "main")
    files = cloud_files()
    log(f"3/5 · Subiendo motor ({len(files)} archivos)…")
    for path, content in files.items():
        gh.put_file(f"{user}/{repo_name}", path, content.encode("utf-8"), branch, f"AutoDiag: {path}")
        log(f"   ✔ {path}")
    log("4/5 · Activando GitHub Actions…")
    gh.req("PUT", f"/repos/{user}/{repo_name}/actions/permissions", ok=False, json={"enabled": True, "allowed_actions": "all"})
    ok = False
    for _ in range(10):
        w = gh.req("GET", f"/repos/{user}/{repo_name}/actions/workflows", ok=False)
        if w.ok and any(x["path"].endswith("render_video.yml") for x in w.json().get("workflows", [])):
            ok = True
            break
        time.sleep(2)
    log("   ✔ Flujo render_video.yml activo" if ok else "   ⚠ El flujo aún no aparece; puede tardar un minuto")
    log(f"5/5 · ✅ ¡Nube configurada!  https://github.com/{user}/{repo_name}")
    return {"owner": user, "repo": repo_name, "branch": branch, "private": private, "cloudReady": True}


def deploy_cloudflare_worker(cf_token, account_id, gh_token, repo_full, app_key, name, log):
    api = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers"
    h = {"Authorization": f"Bearer {cf_token}"}
    code = cloud_files()["worker/worker.js"]
    meta = {"main_module": "worker.js", "compatibility_date": "2024-11-01",
            "bindings": [{"type": "secret_text", "name": "GITHUB_TOKEN", "text": gh_token},
                         {"type": "secret_text", "name": "APP_KEY", "text": app_key},
                         {"type": "plain_text", "name": "GITHUB_REPO", "text": repo_full}]}
    log("1/3 · Subiendo Worker…")
    r = requests.put(f"{api}/scripts/{name}", headers=h, timeout=60,
                     files={"metadata": (None, json.dumps(meta), "application/json"),
                            "worker.js": ("worker.js", code, "application/javascript+module")})
    if not r.ok or not r.json().get("success"):
        raise RuntimeError("Cloudflare: " + r.text[:300])
    log("2/3 · Activando subdominio workers.dev…")
    requests.post(f"{api}/scripts/{name}/subdomain", headers=h, json={"enabled": True}, timeout=30)
    sub = requests.get(f"{api}/subdomain", headers=h, timeout=30).json().get("result", {}).get("subdomain")
    if not sub:
        raise RuntimeError("Tu cuenta no tiene subdominio workers.dev. Créalo en dash.cloudflare.com → Workers.")
    url = f"https://{name}.{sub}.workers.dev"
    log(f"3/3 · ✅ Worker desplegado: {url}")
    return url


class GitHubBackend:
    def __init__(self, p):
        self.gh, self.repo, self.branch = GitHub(p["githubToken"]), f"{p['owner']}/{p['repo']}", p.get("branch", "main")

    def submit(self, job, audio_bytes=None):
        if audio_bytes:
            self.gh.put_file(self.repo, f"jobs/{job['id']}.mp3", audio_bytes, self.branch, "audio " + job["id"])
        self.gh.put_file(self.repo, f"jobs/{job['id']}.json", json.dumps(job, ensure_ascii=False).encode("utf-8"), self.branch, "job " + job["id"])
        self.gh.req("POST", f"/repos/{self.repo}/actions/workflows/render_video.yml/dispatches", json={"ref": self.branch, "inputs": {"job_id": job["id"]}})
        return job["id"]

    def status(self, jid):
        runs = self.gh.req("GET", f"/repos/{self.repo}/actions/runs", params={"event": "workflow_dispatch", "per_page": 40}).json()
        run = next((x for x in runs.get("workflow_runs", []) if x.get("display_title") == f"render {jid}"), None)
        if not run:
            return {"state": "queued", "step": "Esperando a GitHub Actions"}
        if run["status"] != "completed":
            step = run["status"]
            try:
                steps = self.gh.req("GET", f"/repos/{self.repo}/actions/runs/{run['id']}/jobs").json()["jobs"][0]["steps"]
                cur = next((s for s in steps if s["status"] == "in_progress"), None) or [s for s in steps if s["status"] == "completed"][-1]
                step = cur["name"]
            except Exception:
                pass
            return {"state": "running", "step": step, "run_url": run["html_url"]}
        st = self.gh.req("GET", f"/repos/{self.repo}/contents/status.json", ok=False, params={"ref": f"render-{jid}"},
                         headers={"Accept": "application/vnd.github.raw"})
        if st.ok:
            s = st.json()
            return {"state": s["state"], "step": "Completado" if s["state"] == "ok" else "Error", "log": s.get("log", ""), "run_url": run["html_url"]}
        return {"state": "running" if run["conclusion"] == "success" else "error", "step": run["conclusion"], "run_url": run["html_url"]}

    def download(self, jid, dest):
        r = self.gh.s.get(f"https://api.github.com/repos/{self.repo}/contents/final.mp4", params={"ref": f"render-{jid}"},
                          headers={"Accept": "application/vnd.github.raw"}, stream=True, timeout=300)
        if not r.ok:
            raise RuntimeError(f"No se pudo descargar ({r.status_code})")
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)

    def cleanup(self, jid):
        self.gh.req("DELETE", f"/repos/{self.repo}/git/refs/heads/render-{jid}", ok=False)


class ProxyBackend:
    def __init__(self, p):
        self.url, self.h = p["proxyUrl"].rstrip("/"), {"X-App-Key": p.get("proxyKey", "")}

    def _j(self, method, path, **kw):
        r = requests.request(method, self.url + path, headers=self.h, timeout=180, **kw)
        d = r.json() if r.content else {}
        if not r.ok:
            raise RuntimeError(d.get("error", r.status_code))
        return d

    def submit(self, job, audio_bytes=None):
        body = {"job": job}
        if audio_bytes:
            body["audio_b64"] = base64.b64encode(audio_bytes).decode()
        return self._j("POST", "/api/jobs", json=body)["id"]

    def status(self, jid):
        return self._j("GET", f"/api/jobs/{jid}")

    def download(self, jid, dest):
        r = requests.get(f"{self.url}/api/jobs/{jid}/video", headers=self.h, stream=True, timeout=300)
        if not r.ok:
            raise RuntimeError("No se pudo descargar")
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)

    def cleanup(self, jid):
        try:
            self._j("DELETE", f"/api/jobs/{jid}")
        except Exception:
            pass


def render_job(profile, job, audio_path, progress):
    """Envía el trabajo, espera, descarga a Videos_Listos. Devuelve la ruta del MP4."""
    if profile.get("backend") == "proxy":
        if not profile.get("proxyUrl"):
            raise RuntimeError("Configura la URL del servidor en ⚙️ Cuentas")
        be = ProxyBackend(profile)
    else:
        if not profile.get("cloudReady"):
            raise RuntimeError("Primero pulsa 🚀 Auto-Configurar mi Nube en ⚙️ Cuentas")
        be = GitHubBackend(profile)
    audio = open(audio_path, "rb").read() if audio_path else None
    progress("Enviando trabajo a la nube…")
    jid = be.submit(job, audio)
    t0 = time.time()
    while True:
        time.sleep(6)
        try:
            st = be.status(jid)
        except Exception as e:
            st = {"state": "running", "step": f"Reintentando: {e}"}
        secs = int(time.time() - t0)
        progress(f"⏳ {st.get('step') or st.get('state')} · {secs // 60}:{secs % 60:02d}")
        if st["state"] in ("ok", "error"):
            break
        if secs > 3600:
            raise RuntimeError("Tiempo de espera agotado")
    if st["state"] == "error":
        raise RuntimeError("El render falló. " + (st.get("run_url") or "") + "\n" + (st.get("log") or "")[-1500:])
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    name = re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ-]+", "_", job.get("titulo") or "video")[:40] + f"_{job['formato'].replace(':', 'x')}_{jid}.mp4"
    dest = os.path.join(VIDEOS_DIR, name)
    progress("⬇️ Descargando MP4…")
    be.download(jid, dest)
    be.cleanup(jid)
    return dest


def make_job(data, formato, fps, voz, velocidad, plantilla, estilo="osciloscopio", extras=None):
    job = json.loads(json.dumps(data))
    job.update({"id": "ad" + format(int(time.time() * 1000), "x"), "formato": formato, "fps": int(fps), "voz": voz,
                "velocidad": velocidad, "plantilla": plantilla, "estilo": estilo, "modo": "libre" if job.get("codigo_libre") else "plantilla",
                "created": datetime.now().isoformat(timespec="seconds")})
    if estilo == "pastillas":
        ex = extras or {}
        job.update({"categoria": ex.get("categoria") or "DIAGNÓSTICO AUTOMOTRIZ", "categoria_portada": ex.get("categoriaPortada") or "DIAGNÓSTICO AUTOMOTRIZ",
                    "cta_texto": ex.get("ctaTexto") or "Información en mi perfil", "cta_boton": ex.get("ctaBoton") or "", "subtitulos": False})
    job["marcas_tiempo_estimadas"] = estimate_timeline(job)
    return job


# ================================================================= INTERFAZ
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} · Multi-User Edition {VERSION}")
        self.geometry("1180x800")
        self.minsize(980, 680)
        self.configure(fg_color=C["bg"])
        try:
            self.iconbitmap(os.path.join(RES_DIR, "icon.ico"))
        except Exception:
            pass
        self.store = load_store()
        self.data = None
        self.audio_path = None
        self.excel_path = None
        self.F = ctk.CTkFont(family="Segoe UI", size=14)
        self.FB = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        self.FM = ctk.CTkFont(family="Consolas", size=12)
        self.FT = ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        self._header()
        self.tabs = ctk.CTkTabview(self, fg_color=C["panel"], segmented_button_selected_color=C["orange"],
                                   segmented_button_selected_hover_color="#ff7a3a", corner_radius=14)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._studio(self.tabs.add("🎬 Estudio de Creación"))
        self._batch(self.tabs.add("📊 Lote desde Excel"))
        self._accounts(self.tabs.add("⚙️ Configurar Cuentas"))
        self.load_profile_into_ui()
        if not (self.P().get("geminiOk") and self.P().get("cloudReady")):
            self.tabs.set("⚙️ Configurar Cuentas")

    # ------------------------------------------------------------- helpers
    def P(self):
        return self.store["profiles"].setdefault(self.store["active"], {})

    def save(self):
        save_store(self.store)

    def ui(self, fn, *a):
        self.after(0, lambda: fn(*a))

    def btn(self, parent, text, cmd, kind="normal", **kw):
        colors = {"pri": (C["orange"], "#ff7a3a", "#ffffff"), "cy": (C["panel2"], "#12313a", C["cyan"]), "normal": (C["panel2"], "#1d2b42", C["text"])}[kind]
        return ctk.CTkButton(parent, text=text, command=cmd, fg_color=colors[0], hover_color=colors[1], text_color=colors[2],
                             border_color=C["border"] if kind != "cy" else C["cyan"], border_width=1, corner_radius=10, font=self.FB, height=38, **kw)

    def label(self, parent, text, **kw):
        return ctk.CTkLabel(parent, text=text, font=self.FM, text_color=C["dim"], anchor="w", **kw)

    def thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ------------------------------------------------------------- copiar / pegar (clic derecho + Ctrl+V en cualquier teclado)
    def _inner(self, w):
        return getattr(w, "_entry", None) or getattr(w, "_textbox", None) or w

    def paste_into(self, w):
        inner = self._inner(w)
        try:
            txt = self.clipboard_get()
        except Exception:
            return "break"
        if isinstance(w, ctk.CTkEntry):
            txt = txt.strip()
        try:
            inner.delete("sel.first", "sel.last")
        except Exception:
            pass
        inner.insert("insert", txt)
        try:
            inner.event_generate("<FocusOut>")
        except Exception:
            pass
        return "break"

    def copy_from(self, w, cut=False):
        inner = self._inner(w)
        try:
            sel = inner.selection_get()
        except Exception:
            return "break"
        self.clipboard_clear()
        self.clipboard_append(sel)
        if cut:
            try:
                inner.delete("sel.first", "sel.last")
            except Exception:
                pass
        return "break"

    def select_all(self, w):
        inner = self._inner(w)
        try:
            if isinstance(w, ctk.CTkEntry):
                inner.select_range(0, "end"); inner.icursor("end")
            else:
                inner.tag_add("sel", "1.0", "end")
        except Exception:
            pass
        return "break"

    def enable_clipboard(self, w):
        inner = self._inner(w)
        menu = tk.Menu(self, tearoff=0, bg=C["panel"], fg=C["text"], activebackground=C["orange"], activeforeground="#fff", font=("Segoe UI", 11))
        menu.add_command(label="📋 Pegar", command=lambda: self.paste_into(w))
        menu.add_command(label="Copiar", command=lambda: self.copy_from(w))
        menu.add_command(label="Cortar", command=lambda: self.copy_from(w, True))
        menu.add_separator()
        menu.add_command(label="Seleccionar todo", command=lambda: self.select_all(w))

        def popup(ev):
            inner.focus_set()
            menu.tk_popup(ev.x_root, ev.y_root)
            menu.grab_release()
            return "break"

        def keys(ev):
            if not (ev.state & 0x4):  # Ctrl presionado
                return None
            k = ev.keycode
            if k == 86: return self.paste_into(w)          # V
            if k == 67: return self.copy_from(w)           # C
            if k == 88: return self.copy_from(w, True)     # X
            if k == 65: return self.select_all(w)          # A
            return None
        inner.bind("<Button-3>", popup)
        inner.bind("<Control-KeyPress>", keys)
        inner.bind("<Shift-Insert>", lambda e: self.paste_into(w))

    def secret_row(self, parent, entry_kwargs):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        e = ctk.CTkEntry(row, show="•", font=self.F, **entry_kwargs)
        e.pack(side="left", fill="x", expand=True)
        self.btn(row, "📋 Pegar", lambda: self.paste_into(e), "cy", width=90).pack(side="left", padx=(6, 0))
        eye = {"on": False}

        def toggle():
            eye["on"] = not eye["on"]
            e.configure(show="" if eye["on"] else "•")
        self.btn(row, "👁", toggle, width=44).pack(side="left", padx=(6, 0))
        return row, e

    # ------------------------------------------------------------- cabecera
    def _header(self):
        h = ctk.CTkFrame(self, fg_color=C["bg"])
        h.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(h, text="⚡ AutoDiag Video Studio", font=self.FT, text_color=C["text"]).pack(side="left")
        self.led_cloud = ctk.CTkLabel(h, text="● NUBE", font=self.FM, text_color=C["red"])
        self.led_cloud.pack(side="right", padx=6)
        self.led_gem = ctk.CTkLabel(h, text="● GEMINI", font=self.FM, text_color=C["red"])
        self.led_gem.pack(side="right", padx=6)
        self.profile_var = ctk.StringVar(value=self.store["active"])
        self.profile_menu = ctk.CTkOptionMenu(h, variable=self.profile_var, values=list(self.store["profiles"]), command=self.switch_profile,
                                              fg_color=C["panel2"], button_color=C["panel"], font=self.F)
        self.profile_menu.pack(side="right", padx=14)
        ctk.CTkLabel(h, text="Perfil:", font=self.FM, text_color=C["dim"]).pack(side="right")

    def refresh_leds(self):
        p = self.P()
        self.led_gem.configure(text_color=C["green"] if p.get("geminiOk") else C["red"])
        ready = p.get("proxyOk") if p.get("backend") == "proxy" else p.get("cloudReady")
        self.led_cloud.configure(text_color=C["green"] if ready else C["red"])
        self.g_status.configure(text="🟢 Conectado" if p.get("geminiOk") else "🔴 Pendiente")
        self.gh_status.configure(text=f"🟢 Conectado a {p.get('owner')}/{p.get('repo')}" if p.get("cloudReady") else "🔴 Pendiente")

    # ------------------------------------------------------------- Estudio
    def _studio(self, tab):
        tab.grid_columnconfigure(0, weight=3)
        tab.grid_columnconfigure(1, weight=2)
        tab.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ctk.CTkFrame(tab, fg_color=C["panel2"], corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew")

        self.label(left, "IDEA O GUION").pack(fill="x", pady=(4, 2))
        self.idea = ctk.CTkTextbox(left, height=90, font=self.F, fg_color=C["panel2"], border_color=C["border"], border_width=1)
        self.idea.pack(fill="x")
        self.exact_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(left, text="Es mi guion exacto (no reescribir)", variable=self.exact_var, font=self.F).pack(anchor="w", pady=6)

        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", pady=4)
        self.fmt_var = ctk.StringVar(value="9:16")
        col = ctk.CTkFrame(row, fg_color="transparent"); col.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.label(col, "FORMATO").pack(fill="x")
        ctk.CTkSegmentedButton(col, values=["9:16", "16:9"], variable=self.fmt_var, selected_color=C["cyan"], selected_hover_color=C["cyan"],
                               text_color="#04121a", font=self.FB).pack(fill="x")
        col = ctk.CTkFrame(row, fg_color="transparent"); col.pack(side="left", fill="x", expand=True, padx=6)
        self.label(col, "PLANTILLA").pack(fill="x")
        self.tpl_var = ctk.StringVar(value=list(TEMPLATES)[0])
        ctk.CTkOptionMenu(col, values=list(TEMPLATES), variable=self.tpl_var, fg_color=C["panel2"], button_color=C["panel"], font=self.F).pack(fill="x")

        row2 = ctk.CTkFrame(left, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        self.voice_var, self.rate_var, self.fps_var = ctk.StringVar(value=list(VOICES)[0]), ctk.StringVar(value="Ágil (reels)"), ctk.StringVar(value="60")
        for title, var, vals in (("VOZ (EDGE-TTS)", self.voice_var, list(VOICES)), ("VELOCIDAD", self.rate_var, list(RATES)), ("FPS", self.fps_var, ["60", "30"])):
            col = ctk.CTkFrame(row2, fg_color="transparent"); col.pack(side="left", fill="x", expand=True, padx=3)
            self.label(col, title).pack(fill="x")
            ctk.CTkOptionMenu(col, values=vals, variable=var, fg_color=C["panel2"], button_color=C["panel"], font=self.F).pack(fill="x")

        row3 = ctk.CTkFrame(left, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        col = ctk.CTkFrame(row3, fg_color="transparent"); col.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.label(col, "ESTILO VISUAL").pack(fill="x")
        self.style_var = ctk.StringVar(value=list(ESTILOS)[0])
        ctk.CTkOptionMenu(col, values=list(ESTILOS), variable=self.style_var, fg_color=C["panel2"], button_color=C["panel"], font=self.F).pack(fill="x")
        col = ctk.CTkFrame(row3, fg_color="transparent"); col.pack(side="left", padx=6)
        self.label(col, "VOZ REAL (EDGE-TTS)").pack(fill="x")
        self.btn(col, "🔊 Probar voz", self.test_voice, "cy").pack(fill="x")

        self.past_frame = ctk.CTkFrame(left, fg_color=C["panel2"], corner_radius=10)
        self.past_entries = {}
        for i, (key, title, ph) in enumerate((("categoria", "ETIQUETA SUPERIOR", "DIAGNÓSTICO DIÉSEL"), ("categoriaPortada", "ETIQUETA DE PORTADA", "DIAGNÓSTICO AUTOMOTRIZ"),
                                              ("ctaTexto", "CIERRE: TEXTO", "Información en mi perfil"), ("ctaBoton", "CIERRE: BOTÓN", "Módulo 0 gratis"))):
            cell = ctk.CTkFrame(self.past_frame, fg_color="transparent")
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=8, pady=4)
            self.past_frame.grid_columnconfigure(i % 2, weight=1)
            self.label(cell, title).pack(fill="x")
            e = ctk.CTkEntry(cell, placeholder_text=ph, font=self.F)
            e.pack(fill="x")
            e.bind("<FocusOut>", lambda _e: self.save_past_fields())
            self.enable_clipboard(e)
            self.past_entries[key] = e
        self.past_anchor = ctk.CTkFrame(left, fg_color="transparent", height=1)
        self.past_anchor.pack(fill="x")
        self.style_var.trace_add("write", lambda *a: self.toggle_past())

        arow = ctk.CTkFrame(left, fg_color="transparent")
        arow.pack(fill="x", pady=6)
        self.btn(arow, "🎙️ Audio propio (opcional)", self.pick_audio).pack(side="left")
        self.audio_lbl = ctk.CTkLabel(arow, text="Sin audio: se usará Edge-TTS", font=self.F, text_color=C["dim"])
        self.audio_lbl.pack(side="left", padx=10)
        self.btn(left, "✨ Generar guion + animación con Gemini", self.generate, "pri").pack(fill="x", pady=(8, 4))
        self.gen_status = ctk.CTkLabel(left, text="", font=self.FM, text_color=C["yellow"], anchor="w")
        self.gen_status.pack(fill="x")

        self.label(left, "TÍTULO DE PORTADA").pack(fill="x", pady=(10, 2))
        self.titulo = ctk.CTkEntry(left, font=self.F, fg_color=C["panel2"], border_color=C["border"])
        self.titulo.pack(fill="x")
        self.label(left, "GUION DE VOZ").pack(fill="x", pady=(10, 2))
        self.guion = ctk.CTkTextbox(left, height=150, font=self.F, fg_color=C["panel2"], border_color=C["border"], border_width=1)
        self.guion.pack(fill="x")
        self.label(left, "ESCENAS (JSON AVANZADO, EDITABLE)").pack(fill="x", pady=(10, 2))
        self.scenes = ctk.CTkTextbox(left, height=200, font=self.FM, fg_color=C["panel2"], border_color=C["border"], border_width=1)
        self.scenes.pack(fill="x")
        brow = ctk.CTkFrame(left, fg_color="transparent")
        brow.pack(fill="x", pady=8)
        for w in (self.idea, self.titulo, self.guion, self.scenes):
            self.enable_clipboard(w)
        self.btn(brow, "📋 Pegar texto narrado", lambda: (self.idea.delete("1.0", "end"), self.paste_into(self.idea), self.guion.delete("1.0", "end"), self.paste_into(self.guion), self.exact_var.set(True))).pack(side="left", padx=(0, 6))
        self.btn(brow, "📋 Copiar guion", self.copy_guion).pack(side="left", padx=(0, 6))
        brow2 = ctk.CTkFrame(left, fg_color="transparent")
        brow2.pack(fill="x", pady=(0, 8))
        self.btn(brow2, "🤖 Generar prompt (desde Guion)", self.copy_scene_prompt, "cy").pack(side="left", padx=(0, 6))
        self.btn(brow2, "✅ Aplicar escenas pegadas", self.apply_scenes, "cy").pack(side="left", padx=6)
        self.btn(brow, "⬇️ Guardar HTML HyperFrames", self.save_html).pack(side="left", padx=6)

        ctk.CTkLabel(right, text="VISTA PREVIA Y RENDER", font=self.FB, text_color=C["dim"]).pack(pady=(16, 6))
        ctk.CTkLabel(right, text="La vista previa se abre en tu navegador\n(animación en tiempo real con tiempos estimados).",
                     font=self.F, text_color=C["dim"]).pack(pady=4)
        self.btn(right, "👁️ Previsualizar animación", self.preview, "cy").pack(fill="x", padx=16, pady=8)
        self.btn(right, "🎬 Renderizar y Descargar MP4", self.render_one, "pri").pack(fill="x", padx=16, pady=8)
        self.prog = ctk.CTkProgressBar(right, progress_color=C["orange"])
        self.prog.pack(fill="x", padx=16, pady=6)
        self.prog.set(0)
        self.r_status = ctk.CTkLabel(right, text="Listo para renderizar", font=self.FM, text_color=C["text"], wraplength=380, justify="left")
        self.r_status.pack(fill="x", padx=16, pady=6)
        self.btn(right, "📂 Abrir carpeta Videos_Listos", self.open_videos).pack(fill="x", padx=16, pady=(20, 8))

    def past_fields(self):
        return {k: e.get().strip() for k, e in getattr(self, "past_entries", {}).items()}

    def save_past_fields(self):
        p = self.P()
        p.update(self.past_fields())
        p["estilo"] = ESTILOS.get(self.style_var.get(), "osciloscopio")
        self.save()

    def toggle_past(self):
        if ESTILOS.get(self.style_var.get()) == "pastillas":
            self.past_frame.pack(fill="x", pady=4, after=self.past_anchor)
        else:
            self.past_frame.pack_forget()
        self.save_past_fields()

    def pick_audio(self):
        p = filedialog.askopenfilename(title="Audio de narración", filetypes=[("Audio", "*.mp3 *.m4a *.wav *.ogg"), ("Todos", "*.*")])
        self.audio_path = p or None
        self.audio_lbl.configure(text=os.path.basename(p) if p else "Sin audio: se usará Edge-TTS")

    def current_data(self):
        try:
            extra = parse_scenes_text(self.scenes.get("1.0", "end"))
        except Exception as e:
            raise RuntimeError(f"JSON de escenas inválido: {e}")
        base = self.data or {}
        if not base and not extra.get("escenas"):
            raise RuntimeError("Genera con Gemini o pega las escenas en el cuadro ESCENAS")
        d = normalize({**base, **extra})
        t = self.titulo.get().strip()
        if t:
            d["titulo"] = t
        g = self.guion.get("1.0", "end").strip()
        if g and g != getattr(self, "shown_guion", "") and g != d["guion_voz"]:
            words, counts = g.split(), [len(s["texto"].split()) for s in d["escenas"]]
            tot, k = sum(counts) or 1, 0
            for i, s in enumerate(d["escenas"]):
                n = len(words) - k if i == len(d["escenas"]) - 1 else max(1, round(counts[i] / tot * len(words)))
                s["texto"] = " ".join(words[k:k + n])
                k += n
            d["guion_voz"] = g
        return d

    def job_from_ui(self):
        return make_job(self.current_data(), self.fmt_var.get(), self.fps_var.get(), VOICES[self.voice_var.get()],
                        RATES[self.rate_var.get()], TEMPLATES[self.tpl_var.get()], ESTILOS[self.style_var.get()], self.past_fields())

    def show_data(self, d):
        self.data = d
        self.shown_guion = d.get("guion_voz", "")
        self.titulo.delete(0, "end"); self.titulo.insert(0, d.get("titulo", ""))
        self.guion.delete("1.0", "end"); self.guion.insert("1.0", d.get("guion_voz", ""))
        show = {"titulo": d.get("titulo"), "subtitulo": d.get("subtitulo"), "escenas": d["escenas"]}
        if d.get("codigo_libre"):
            show["codigo_libre"] = d["codigo_libre"]
        self.scenes.delete("1.0", "end"); self.scenes.insert("1.0", json.dumps(show, ensure_ascii=False, indent=2))

    def generate(self):
        idea = self.idea.get("1.0", "end").strip() or self.guion.get("1.0", "end").strip()
        p = self.P()
        if not idea:
            return messagebox.showwarning(APP_NAME, "Escribe la idea o pega tu guion")
        if not p.get("geminiKey"):
            return messagebox.showwarning(APP_NAME, "Configura tu GEMINI_API_KEY en ⚙️ Configurar Cuentas")
        self.gen_status.configure(text="⏳ Gemini está escribiendo el guion y diseñando las escenas…", text_color=C["yellow"])

        def work():
            try:
                d = normalize(gemini_generate(p["geminiKey"], p.get("model", "gemini-2.5-flash"),
                                              build_prompt(idea, TEMPLATES[self.tpl_var.get()], self.exact_var.get(), self.fmt_var.get(), ESTILOS[self.style_var.get()])), idea)
                self.ui(self.show_data, d)
                self.ui(lambda: self.gen_status.configure(text=f"✅ Listo: {len(d['escenas'])} escenas", text_color=C["green"]))
                self.ui(self.preview)
            except Exception as e:
                self.ui(lambda: self.gen_status.configure(text=f"❌ {e}", text_color=C["red"]))
        self.thread(work)

    def preview(self):
        try:
            job = self.job_from_ui()
        except Exception as e:
            return messagebox.showwarning(APP_NAME, str(e))
        html = build_html(job, job["marcas_tiempo_estimadas"], preview=True)
        html = html.replace("<body>", '<body><div style="position:fixed;top:8px;left:8px;z-index:9;color:#7F92AE;font:12px Consolas">AutoDiag · vista previa (clic = pausa)</div>', 1)
        path = os.path.join(tempfile.gettempdir(), "autodiag_preview.html")
        open(path, "w", encoding="utf-8").write(html)
        webbrowser.open("file:///" + path.replace("\\", "/"))

    def save_html(self):
        try:
            job = self.job_from_ui()
        except Exception as e:
            return messagebox.showwarning(APP_NAME, str(e))
        p = filedialog.asksaveasfilename(defaultextension=".html", initialfile="index.html", filetypes=[("HTML", "*.html")])
        if p:
            open(p, "w", encoding="utf-8").write(build_html(job, job["marcas_tiempo_estimadas"]))

    def copy_scene_prompt(self):
        texto = self.guion.get("1.0", "end").strip() or self.idea.get("1.0", "end").strip()
        if not texto:
            return messagebox.showwarning(APP_NAME, "Pega primero tu texto narrado en la casilla GUION DE VOZ")
        self.clipboard_clear()
        self.clipboard_append(build_prompt(texto, TEMPLATES[self.tpl_var.get()], True, self.fmt_var.get(), ESTILOS[self.style_var.get()]))
        self.r_status.configure(text="🤖 Prompt copiado. Pégalo en Claude o Gemini y pega su respuesta en ESCENAS.", text_color=C["cyan"])

    def test_voice(self):
        texto = self.guion.get("1.0", "end").strip() or self.idea.get("1.0", "end").strip()
        texto = texto[:260] if texto else "Hola, esta es la voz que tendrá tu video de diagnóstico automotriz."
        voz, rate = VOICES[self.voice_var.get()], RATES[self.rate_var.get()]
        self.r_status.configure(text="🔊 Generando muestra de voz…", text_color=C["yellow"])

        def work():
            try:
                import asyncio
                import edge_tts
                out = os.path.join(tempfile.gettempdir(), "autodiag_prueba_voz.mp3")
                asyncio.run(edge_tts.Communicate(texto, voz, rate=rate).save(out))
                if os.name == "nt":
                    os.startfile(out)
                else:
                    webbrowser.open("file://" + out)
                self.ui(lambda: self.r_status.configure(text=f"🔊 Reproduciendo {self.voice_var.get()} ({self.rate_var.get()})", text_color=C["green"]))
            except Exception as e:
                self.ui(lambda: self.r_status.configure(text=f"❌ No se pudo generar la voz: {e}", text_color=C["red"]))
        self.thread(work)

    def apply_scenes(self):
        try:
            d = self.current_data()
        except Exception as e:
            return messagebox.showwarning(APP_NAME, str(e))
        self.show_data(d)
        self.r_status.configure(text=f"✅ {len(d['escenas'])} escenas aplicadas. Ya puedes previsualizar o renderizar.", text_color=C["green"])

    def copy_guion(self):
        self.clipboard_clear()
        self.clipboard_append(self.guion.get("1.0", "end").strip())
        self.r_status.configure(text="📋 Guion copiado")

    def open_videos(self):
        os.makedirs(VIDEOS_DIR, exist_ok=True)
        os.startfile(VIDEOS_DIR) if os.name == "nt" else webbrowser.open("file://" + VIDEOS_DIR)

    def render_one(self):
        try:
            job = self.job_from_ui()
        except Exception as e:
            return messagebox.showwarning(APP_NAME, str(e))
        p = dict(self.P())
        self.prog.configure(mode="indeterminate"); self.prog.start()

        def work():
            try:
                dest = render_job(p, job, self.audio_path, lambda s: self.ui(lambda: self.r_status.configure(text=s)))
                self.ui(lambda: self.r_status.configure(text=f"✅ Guardado en Videos_Listos:\n{os.path.basename(dest)}", text_color=C["green"]))
            except Exception as e:
                self.ui(lambda: self.r_status.configure(text=f"❌ {e}", text_color=C["red"]))
            self.ui(lambda: (self.prog.stop(), self.prog.configure(mode="determinate"), self.prog.set(1)))
        self.r_status.configure(text_color=C["text"])
        self.thread(work)

    # ------------------------------------------------------------- Lote Excel
    def _batch(self, tab):
        ctk.CTkLabel(tab, text="Procesa muchos videos a la vez desde un Excel (.xlsx) o CSV.", font=self.F, text_color=C["dim"]).pack(anchor="w", pady=(8, 4))
        ctk.CTkLabel(tab, text="Columnas: ID · Tema_Tecnico · Guion_Audio · Formato_9_16_o_16_9 · Plantilla · Estado · Archivo_MP4",
                     font=self.FM, text_color=C["cyan"]).pack(anchor="w", pady=4)
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", pady=8)
        self.btn(row, "📊 Generar Plantilla Excel", self.make_template).pack(side="left", padx=(0, 8))
        self.btn(row, "📂 Elegir archivo…", self.pick_excel).pack(side="left", padx=8)
        self.btn(row, "▶️ Procesar Lote Excel", self.run_batch, "pri").pack(side="left", padx=8)
        self.excel_lbl = ctk.CTkLabel(tab, text="Ningún archivo seleccionado", font=self.F, text_color=C["dim"], anchor="w")
        self.excel_lbl.pack(fill="x", pady=4)
        self.batch_prog = ctk.CTkProgressBar(tab, progress_color=C["orange"])
        self.batch_prog.pack(fill="x", pady=6)
        self.batch_prog.set(0)
        self.batch_log = ctk.CTkTextbox(tab, font=self.FM, fg_color="#050A12", text_color="#9fb3cc")
        self.batch_log.pack(fill="both", expand=True, pady=6)

    def blog(self, s):
        self.ui(lambda: (self.batch_log.insert("end", s + "\n"), self.batch_log.see("end")))

    def make_template(self):
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.worksheet.datavalidation import DataValidation
        p = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="Lote_AutoDiag.xlsx", filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "Videos"
        heads = ["ID", "Tema_Tecnico", "Guion_Audio", "Formato_9_16_o_16_9", "Plantilla", "Estado", "Archivo_MP4"]
        ws.append(heads)
        ws.append([1, "Cómo probar un sensor CKP inductivo y ver el diente faltante en el osciloscopio", "", "9:16", "osciloscopio", "", ""])
        ws.append([2, "Prueba del relé de la bomba de combustible: pines 30, 85, 86 y 87", "", "9:16", "rele", "", ""])
        ws.append([3, "Inyector: lectura del pico inductivo y qué indica si no aparece", "", "16:9", "pwm", "", ""])
        ws.append([4, "Pinout de la ECU: alimentación, masas y red CAN", "", "9:16", "pinout", "", ""])
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="F76015")
            c.alignment = Alignment(horizontal="center")
        for col, w in zip("ABCDEFG", (6, 60, 60, 20, 16, 22, 50)):
            ws.column_dimensions[col].width = w
        dv1 = DataValidation(type="list", formula1='"9:16,16:9"', allow_blank=True)
        dv2 = DataValidation(type="list", formula1='"auto,osciloscopio,pwm,rele,pinout,libre"', allow_blank=True)
        ws.add_data_validation(dv1); ws.add_data_validation(dv2)
        dv1.add("D2:D500"); dv2.add("E2:E500")
        ws.freeze_panes = "A2"
        info = wb.create_sheet("Instrucciones")
        for line in ["Llena una fila por video.", "Tema_Tecnico: la idea (Gemini escribe el guion).",
                     "Guion_Audio: si lo llenas, se usa EXACTO como narración.", "Formato: 9:16 (Reels/TikTok) o 16:9 (cursos).",
                     "Plantilla: auto, osciloscopio, pwm, rele, pinout o libre.",
                     "Estado: lo escribe la app (✅ Completado / ❌ Error). Las filas completadas se saltan.",
                     "Los MP4 se guardan en la carpeta Videos_Listos junto al programa."]:
            info.append([line])
        info.column_dimensions["A"].width = 90
        wb.save(p)
        self.excel_path = p
        self.excel_lbl.configure(text=p)
        messagebox.showinfo(APP_NAME, "Plantilla creada:\n" + p)

    def pick_excel(self):
        p = filedialog.askopenfilename(filetypes=[("Excel o CSV", "*.xlsx *.csv")])
        if p:
            self.excel_path = p
            self.excel_lbl.configure(text=p)

    def run_batch(self):
        if not self.excel_path:
            return messagebox.showwarning(APP_NAME, "Elige o genera primero el archivo Excel")
        p = dict(self.P())
        if not p.get("geminiKey"):
            return messagebox.showwarning(APP_NAME, "Configura Gemini en ⚙️ Configurar Cuentas")
        voz, rate, fps, est = VOICES[self.voice_var.get()], RATES[self.rate_var.get()], self.fps_var.get(), ESTILOS[self.style_var.get()]
        self.thread(lambda: self._batch_worker(p, voz, rate, fps, est))

    def _batch_worker(self, p, voz, rate, fps, est="osciloscopio"):
        path = self.excel_path
        is_csv = path.lower().endswith(".csv")
        try:
            if is_csv:
                rows = list(csv.reader(open(path, encoding="utf-8-sig")))
                heads = rows[0]
                for need in ("Estado", "Archivo_MP4"):
                    if need not in heads:
                        heads.append(need)
                        for r in rows[1:]:
                            r.append("")
                for r in rows[1:]:
                    while len(r) < len(heads):
                        r.append("")
                get = lambda r, k: r[heads.index(k)] if k in heads else ""

                def setv(r, k, v):
                    r[heads.index(k)] = v
                    w = csv.writer(open(path, "w", encoding="utf-8-sig", newline=""))
                    w.writerows(rows)
                items = rows[1:]
            else:
                from openpyxl import load_workbook
                wb = load_workbook(path)
                ws = wb["Videos"] if "Videos" in wb.sheetnames else wb.active
                heads = [str(c.value or "").strip() for c in ws[1]]
                for need in ("Estado", "Archivo_MP4"):
                    if need not in heads:
                        heads.append(need)
                        ws.cell(row=1, column=len(heads), value=need)
                items = list(range(2, ws.max_row + 1))
                get = lambda r, k: (ws.cell(row=r, column=heads.index(k) + 1).value or "") if k in heads else ""

                def setv(r, k, v):
                    ws.cell(row=r, column=heads.index(k) + 1, value=v)
                    try:
                        wb.save(path)
                    except PermissionError:
                        self.blog("   ⚠ Cierra el Excel para que la app pueda escribir el estado")
            todo = [r for r in items if str(get(r, "Tema_Tecnico") or get(r, "Guion_Audio")).strip()
                    and not str(get(r, "Estado")).startswith("✅")]
            self.blog(f"📊 {len(todo)} videos pendientes en {os.path.basename(path)}")
            for n, r in enumerate(todo, 1):
                tema, guion = str(get(r, "Tema_Tecnico")).strip(), str(get(r, "Guion_Audio")).strip()
                fmt = "16:9" if "16" in str(get(r, "Formato_9_16_o_16_9")).split(":")[0] else "9:16"
                tpl = str(get(r, "Plantilla") or "auto").strip().lower()
                tpl = tpl if tpl in TEMPLATES.values() else "auto"
                vid = get(r, "ID") or n
                self.blog(f"\n▶ [{n}/{len(todo)}] ID {vid}: {tema[:70]}")
                self.ui(self.batch_prog.set, (n - 1) / len(todo))
                try:
                    setv(r, "Estado", "⏳ Generando guion…")
                    idea = guion if guion else tema
                    d = normalize(gemini_generate(p["geminiKey"], p.get("model", "gemini-2.5-flash"), build_prompt(idea, tpl, bool(guion), fmt, est)), idea)
                    self.blog(f"   ✔ Guion: {len(d['guion_voz'].split())} palabras, {len(d['escenas'])} escenas")
                    job = make_job(d, fmt, fps, voz, rate, tpl, est, p)
                    setv(r, "Estado", "⏳ Renderizando…")
                    dest = render_job(p, job, None, lambda s: self.blog("   " + s) if ("Descargando" in s or "Enviando" in s) else None)
                    setv(r, "Archivo_MP4", dest)
                    setv(r, "Estado", "✅ Completado")
                    self.blog(f"   ✅ {os.path.basename(dest)}")
                except Exception as e:
                    setv(r, "Estado", f"❌ Error: {str(e)[:120]}")
                    self.blog(f"   ❌ {e}")
            self.ui(self.batch_prog.set, 1)
            self.blog("\n🏁 Lote terminado. Videos en: " + VIDEOS_DIR)
        except Exception as e:
            self.blog(f"❌ No se pudo procesar el archivo: {e}")

    # ------------------------------------------------------------- Cuentas
    def _accounts(self, tab):
        sc = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        sc.pack(fill="both", expand=True)

        def card(title):
            f = ctk.CTkFrame(sc, fg_color=C["panel2"], corner_radius=14, border_color=C["border"], border_width=1)
            f.pack(fill="x", pady=8, padx=4)
            ctk.CTkLabel(f, text=title, font=self.FB, text_color=C["text"], anchor="w").pack(fill="x", padx=14, pady=(12, 4))
            return f

        f = card("👤 Perfiles (cada persona con sus propias cuentas)")
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(0, 12))
        self.prof_name = ctk.CTkEntry(r, placeholder_text="Nombre del perfil (ej. Perfil Pedro)", font=self.F)
        self.prof_name.pack(side="left", fill="x", expand=True)
        self.btn(r, "➕ Nuevo", self.prof_new).pack(side="left", padx=4)
        self.btn(r, "✏️ Renombrar", self.prof_ren).pack(side="left", padx=4)
        self.btn(r, "🗑️ Borrar", self.prof_del).pack(side="left", padx=4)

        f = card("① Cerebro IA · Google Gemini")
        self.label(f, "GEMINI_API_KEY").pack(fill="x", padx=14)
        r0, self.g_key = self.secret_row(f, {"placeholder_text": "AIza..."})
        r0.pack(fill="x", padx=14)
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=14, pady=8)
        self.btn(r, "🔑 Obtener mi API Key Gratis", lambda: webbrowser.open("https://aistudio.google.com/app/apikey"), "cy").pack(side="left")
        self.btn(r, "⚡ Probar Conexión", self.test_gemini).pack(side="left", padx=8)
        self.model_var = ctk.StringVar(value="gemini-2.5-flash")
        self.model_menu = ctk.CTkOptionMenu(r, values=["gemini-2.5-flash", "gemini-2.5-pro"], variable=self.model_var,
                                            command=lambda v: (self.P().__setitem__("model", v), self.save()), fg_color=C["panel"], font=self.F)
        self.model_menu.pack(side="left", padx=8)
        self.g_status = ctk.CTkLabel(f, text="🔴 Pendiente", font=self.FM, anchor="w")
        self.g_status.pack(fill="x", padx=14, pady=(0, 12))

        f = card("② Motor de renderizado · GitHub Actions (gratis)")
        self.label(f, "GITHUB_PERSONAL_TOKEN").pack(fill="x", padx=14)
        r0, self.gh_token = self.secret_row(f, {"placeholder_text": "ghp_... o github_pat_..."})
        r0.pack(fill="x", padx=14)
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=14, pady=8)
        self.btn(r, "🔑 Crear Token en 1 Clic", lambda: webbrowser.open("https://github.com/settings/tokens/new?scopes=repo,workflow&description=AutoDiag_Studio"), "cy").pack(side="left")
        ctk.CTkLabel(r, text="En GitHub baja al final y pulsa «Generate token».", font=self.F, text_color=C["dim"]).pack(side="left", padx=10)
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=14)
        self.gh_repo = ctk.CTkEntry(r, font=self.F)
        self.gh_repo.pack(side="left", fill="x", expand=True)
        self.priv_var = ctk.StringVar(value="Privado")
        ctk.CTkSegmentedButton(r, values=["Privado", "Público"], variable=self.priv_var, font=self.F).pack(side="left", padx=8)
        self.btn(f, "🚀 Auto-Configurar mi Nube", self.provision, "pri").pack(fill="x", padx=14, pady=10)
        self.gh_status = ctk.CTkLabel(f, text="🔴 Pendiente", font=self.FM, anchor="w")
        self.gh_status.pack(fill="x", padx=14)
        self.prov_log = ctk.CTkTextbox(f, height=150, font=self.FM, fg_color="#050A12", text_color="#9fb3cc")
        self.prov_log.pack(fill="x", padx=14, pady=(6, 12))

        f = card("③ Motor alternativo (opcional) · Cloudflare Worker / Render")
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=14)
        self.backend_var = ctk.StringVar(value="GitHub Actions directo")
        ctk.CTkSegmentedButton(r, values=["GitHub Actions directo", "Worker / Servidor"], variable=self.backend_var,
                               command=self.set_backend, font=self.F).pack(side="left")
        self.label(f, "CLOUDFLARE ACCOUNT ID  ·  API TOKEN (permiso: Workers Scripts → Edit)").pack(fill="x", padx=14, pady=(10, 0))
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=14)
        self.cf_acc = ctk.CTkEntry(r, placeholder_text="Account ID", font=self.F); self.cf_acc.pack(side="left", fill="x", expand=True)
        self.cf_tok = ctk.CTkEntry(r, placeholder_text="API Token", show="•", font=self.F); self.cf_tok.pack(side="left", fill="x", expand=True, padx=6)
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=14, pady=8)
        self.btn(r, "☁️ Desplegar Worker automáticamente", self.deploy_worker, "cy").pack(side="left")
        self.btn(r, "🔑 Crear token Cloudflare", lambda: webbrowser.open("https://dash.cloudflare.com/profile/api-tokens")).pack(side="left", padx=6)
        self.btn(r, "🟣 Desplegar servidor en Render", self.deploy_render).pack(side="left", padx=6)
        self.label(f, "URL DEL WORKER / SERVIDOR  ·  APP KEY").pack(fill="x", padx=14)
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(0, 6))
        self.px_url = ctk.CTkEntry(r, placeholder_text="https://autodiag-proxy.TU-CUENTA.workers.dev", font=self.F); self.px_url.pack(side="left", fill="x", expand=True)
        self.px_key = ctk.CTkEntry(r, placeholder_text="App Key", show="•", font=self.F); self.px_key.pack(side="left", fill="x", expand=True, padx=6)
        self.btn(r, "⚡ Probar", self.test_proxy).pack(side="left")
        self.cf_log = ctk.CTkLabel(f, text="", font=self.FM, anchor="w", justify="left", wraplength=900)
        self.cf_log.pack(fill="x", padx=14, pady=(0, 12))
        for e in (self.g_key, self.gh_token, self.gh_repo, self.cf_acc, self.cf_tok, self.px_url, self.px_key):
            e.bind("<FocusOut>", lambda _e: self.collect_fields())
        for w in (self.g_key, self.gh_token, self.gh_repo, self.cf_acc, self.cf_tok, self.px_url, self.px_key, self.prof_name):
            self.enable_clipboard(w)

    def collect_fields(self):
        p = self.P()
        new = {"geminiKey": self.g_key.get().strip(), "githubToken": self.gh_token.get().strip(), "repo": self.gh_repo.get().strip() or "autodiag-hyperframes-engine",
               "cfAccount": self.cf_acc.get().strip(), "cfToken": self.cf_tok.get().strip(), "proxyUrl": self.px_url.get().strip().rstrip("/"), "proxyKey": self.px_key.get().strip()}
        if new["geminiKey"] != p.get("geminiKey", ""):
            p["geminiOk"] = False
        if new["githubToken"] != p.get("githubToken", "") or new["repo"] != p.get("repo", new["repo"]):
            p["cloudReady"] = False
        p.update(new)
        self.save()
        self.refresh_leds()

    def load_profile_into_ui(self):
        p = self.P()
        for e, k, d in ((self.g_key, "geminiKey", ""), (self.gh_token, "githubToken", ""), (self.gh_repo, "repo", "autodiag-hyperframes-engine"),
                        (self.cf_acc, "cfAccount", ""), (self.cf_tok, "cfToken", ""), (self.px_url, "proxyUrl", ""), (self.px_key, "proxyKey", "")):
            e.delete(0, "end"); e.insert(0, p.get(k, d))
        if p.get("models"):
            self.model_menu.configure(values=p["models"])
        self.model_var.set(p.get("model", "gemini-2.5-flash"))
        self.priv_var.set("Público" if p.get("private") is False else "Privado")
        for k, e in getattr(self, "past_entries", {}).items():
            e.delete(0, "end"); e.insert(0, p.get(k, ""))
        inv = {v: k for k, v in ESTILOS.items()}
        if hasattr(self, "style_var") and p.get("estilo") in inv:
            self.style_var.set(inv[p["estilo"]])
        self.backend_var.set("Worker / Servidor" if p.get("backend") == "proxy" else "GitHub Actions directo")
        self.profile_menu.configure(values=list(self.store["profiles"]))
        self.profile_var.set(self.store["active"])
        self.refresh_leds()

    def switch_profile(self, name):
        self.collect_fields()
        self.store["active"] = name
        self.save()
        self.load_profile_into_ui()

    def prof_new(self):
        n = self.prof_name.get().strip()
        if not n or n in self.store["profiles"]:
            return messagebox.showwarning(APP_NAME, "Nombre vacío o repetido")
        self.collect_fields()
        self.store["profiles"][n] = {}
        self.store["active"] = n
        self.save(); self.load_profile_into_ui(); self.prof_name.delete(0, "end")

    def prof_ren(self):
        n = self.prof_name.get().strip()
        if not n or n in self.store["profiles"]:
            return messagebox.showwarning(APP_NAME, "Nombre vacío o repetido")
        self.store["profiles"][n] = self.store["profiles"].pop(self.store["active"])
        self.store["active"] = n
        self.save(); self.load_profile_into_ui(); self.prof_name.delete(0, "end")

    def prof_del(self):
        if len(self.store["profiles"]) < 2:
            return messagebox.showwarning(APP_NAME, "Debe quedar al menos un perfil")
        if messagebox.askyesno(APP_NAME, f"¿Borrar el perfil {self.store['active']}?"):
            self.store["profiles"].pop(self.store["active"])
            self.store["active"] = next(iter(self.store["profiles"]))
            self.save(); self.load_profile_into_ui()

    def set_backend(self, v):
        self.P()["backend"] = "proxy" if v.startswith("Worker") else "github"
        self.save(); self.refresh_leds()

    def test_gemini(self):
        self.collect_fields()
        key = self.P().get("geminiKey")
        if not key:
            return messagebox.showwarning(APP_NAME, "Pega tu API Key")
        self.g_status.configure(text="⏳ Probando…")

        def work():
            p = self.P()
            try:
                ms = gemini_models(key)
                p.update({"geminiOk": True, "models": ms})
                if p.get("model") not in ms:
                    p["model"] = "gemini-2.5-flash" if "gemini-2.5-flash" in ms else next((m for m in ms if "flash" in m), ms[0])
                self.save()
                self.ui(lambda: (self.model_menu.configure(values=ms), self.model_var.set(p["model"]), self.refresh_leds()))
            except Exception as e:
                p["geminiOk"] = False
                self.save()
                self.ui(lambda: (self.refresh_leds(), self.g_status.configure(text=f"🔴 Llave inválida: {e}")))
        self.thread(work)

    def provision(self):
        self.collect_fields()
        p = self.P()
        if not p.get("githubToken"):
            return messagebox.showwarning(APP_NAME, "Pega tu GITHUB_PERSONAL_TOKEN")
        self.prov_log.delete("1.0", "end")
        log = lambda s: self.ui(lambda: (self.prov_log.insert("end", s + "\n"), self.prov_log.see("end")))
        self.gh_status.configure(text="⏳ Configurando…")

        def work():
            try:
                res = provision_github(p["githubToken"], p.get("repo") or "autodiag-hyperframes-engine", self.priv_var.get() == "Privado", log)
                p.update(res)
                p.setdefault("backend", "github")
                self.save()
            except Exception as e:
                log(f"❌ {e}")
            self.ui(self.refresh_leds)
        self.thread(work)

    def deploy_worker(self):
        self.collect_fields()
        p = self.P()
        if not (p.get("cfAccount") and p.get("cfToken")):
            return messagebox.showwarning(APP_NAME, "Pega tu Account ID y API Token de Cloudflare")
        if not p.get("cloudReady"):
            return messagebox.showwarning(APP_NAME, "Primero Auto-Configura tu nube en GitHub (paso ②)")
        app_key = p.get("proxyKey") or base64.urlsafe_b64encode(os.urandom(18)).decode().rstrip("=")
        log = lambda s: self.ui(lambda: self.cf_log.configure(text=s))

        def work():
            try:
                url = deploy_cloudflare_worker(p["cfToken"], p["cfAccount"], p["githubToken"], f"{p['owner']}/{p['repo']}", app_key, "autodiag-proxy", log)
                p.update({"proxyUrl": url, "proxyKey": app_key, "proxyOk": True, "backend": "proxy"})
                self.save()
                self.ui(self.load_profile_into_ui)
                log(f"✅ Worker listo y seleccionado como motor: {url}")
            except Exception as e:
                log(f"❌ {e}")
        self.thread(work)

    def deploy_render(self):
        p = self.P()
        if not p.get("cloudReady"):
            return messagebox.showwarning(APP_NAME, "Primero Auto-Configura tu nube en GitHub (paso ②)")
        if p.get("private", True):
            messagebox.showinfo(APP_NAME, "Render necesita el repositorio PÚBLICO. Cámbialo a «Público» y vuelve a pulsar 🚀 Auto-Configurar.\n"
                                          "Al terminar en Render copia la URL del servicio y la variable APP_KEY aquí.")
        webbrowser.open(f"https://render.com/deploy?repo=https://github.com/{p['owner']}/{p['repo']}")

    def test_proxy(self):
        self.collect_fields()
        p = self.P()
        try:
            r = requests.get(p["proxyUrl"] + "/api/jobs/ping", headers={"X-App-Key": p.get("proxyKey", "")}, timeout=20)
            if r.status_code == 401:
                raise RuntimeError("App Key incorrecta")
            p["proxyOk"] = True
            self.cf_log.configure(text="🟢 Servidor conectado")
        except Exception as e:
            p["proxyOk"] = False
            self.cf_log.configure(text=f"🔴 {e}")
        self.save(); self.refresh_leds()


if __name__ == "__main__":
    App().mainloop()
