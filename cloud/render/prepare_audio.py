#!/usr/bin/env python3
"""Genera la voz (Edge-TTS) o procesa el audio subido, y produce timeline.json
con marcas de tiempo palabra por palabra (formato tipo Whisper word-level).

Uso: python3 render/prepare_audio.py <job.json> <carpeta_salida> [audio_subido]
Salida: <out>/voz.mp3  y  <out>/timeline.json
"""
import asyncio
import json
import os
import re
import subprocess
import sys

LEAD = 0.25   # silencio inicial (s) para que la portada respire
TAIL = 0.60   # cola final (s)


def sh(cmd):
    print("[audio] $", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def duration_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def script_tokens(job):
    segs = [s.get("texto", "") for s in job.get("escenas", [])] or [job.get("guion_voz", "")]
    toks, seg_of = [], []
    for i, s in enumerate(segs):
        for w in str(s).split():
            toks.append(w)
            seg_of.append(i)
    return toks, seg_of, len(segs)


def norm(w):
    return re.sub(r"[^\wáéíóúüñ]", "", w.lower())


async def edge_tts_words(text, voice, rate, pitch, out_mp3):
    import edge_tts
    try:
        comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    except TypeError:  # versiones antiguas no aceptan 'boundary'
        comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    words = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                st = chunk["offset"] / 1e7
                words.append({"word": chunk["text"], "start": st, "end": st + chunk["duration"] / 1e7})
    return words


def whisper_words(path, language="es"):
    from faster_whisper import WhisperModel
    model = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    segments, _ = model.transcribe(path, language=language, word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"word": w.word.strip(), "start": float(w.start), "end": float(w.end)})
    return words


def estimate_words(tokens, dur):
    weights = [len(norm(w)) + 2 + (3.5 if re.search(r"[.,;:!?…]$", w) else 0) for w in tokens]
    total = sum(weights) or 1
    t, out = 0.2, []
    usable = max(1.0, dur - 0.4)
    for w, k in zip(tokens, weights):
        d = usable * k / total
        out.append({"word": w, "start": t, "end": t + d * 0.9})
        t += d
    return out


def main():
    job_path, out = sys.argv[1], sys.argv[2]
    uploaded = sys.argv[3] if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    os.makedirs(out, exist_ok=True)
    job = json.load(open(job_path, encoding="utf-8"))
    tokens, seg_of, nseg = script_tokens(job)
    text = " ".join(tokens) or "Sin guion."
    raw = os.path.join(out, "voz_raw.mp3")
    words = []

    if uploaded:
        print("[audio] usando audio subido por el usuario", flush=True)
        sh(["ffmpeg", "-y", "-v", "error", "-i", uploaded, "-ac", "1", "-ar", "44100", raw])
        try:
            words = whisper_words(raw)
        except Exception as e:  # noqa
            print("[audio] whisper no disponible:", e, flush=True)
    else:
        voice = job.get("voz") or "es-MX-JorgeNeural"
        rate = job.get("velocidad") or "+0%"
        pitch = job.get("tono") or "+0Hz"
        print(f"[audio] Edge-TTS voz={voice} rate={rate}", flush=True)
        words = asyncio.run(edge_tts_words(text, voice, rate, pitch, raw))
        if not words:
            try:
                words = whisper_words(raw)
            except Exception as e:  # noqa
                print("[audio] sin marcas de Edge-TTS y sin whisper:", e, flush=True)

    # normalizar volumen + silencio inicial
    voz = os.path.join(out, "voz.mp3")
    sh(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af",
        f"adelay={int(LEAD * 1000)}:all=1,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-b:a", "192k", voz])
    adur = duration_of(voz)

    if not words:
        words = estimate_words(tokens, adur - LEAD)
    for w in words:
        w["start"] = round(w["start"] + LEAD, 3)
        w["end"] = round(w["end"] + LEAD, 3)

    # Alinear las palabras de la voz con las del guion (difflib): cada palabra sabe a qué escena pertenece,
    # aunque la voz lea números o símbolos con otra cantidad de palabras.
    import difflib
    a = [norm(w["word"]) for w in words]
    b = [norm(t) for t in tokens]
    idx = [None] * len(a)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                idx[i1 + k] = j1 + k
                words[i1 + k]["word"] = tokens[j1 + k]
        elif tag == "replace":
            for k in range(i2 - i1):
                idx[i1 + k] = j1 + min(j2 - j1 - 1, int(k * (j2 - j1) / max(1, i2 - i1)))
    last = 0
    for k in range(len(idx)):
        if idx[k] is None:
            idx[k] = last
        last = idx[k]
    matched = sum(1 for op in sm.get_opcodes() if op[0] == "equal" for _ in range(op[2] - op[1]))
    print(f"[audio] alineación voz/guion: {matched}/{len(a)} palabras coinciden", flush=True)
    for k, w in enumerate(words):
        w["seg"] = seg_of[min(len(seg_of) - 1, idx[k])] if seg_of else 0

    dur = round(adur + TAIL, 3)
    scenes = []
    for i in range(nseg):
        first = next((w for w in words if w["seg"] == i), None)
        scenes.append({"start": first["start"] if first else None})
    for i, s in enumerate(scenes):
        if s["start"] is None:
            s["start"] = scenes[i - 1]["start"] + 1 if i else 0
    scenes[0]["start"] = 0
    for i, s in enumerate(scenes):
        s["end"] = scenes[i + 1]["start"] if i < nseg - 1 else dur

    timeline = {"duration": dur, "language": "es", "words": words, "scenes": scenes,
                "source": "upload+whisper" if uploaded else "edge-tts"}
    json.dump(timeline, open(os.path.join(out, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[audio] listo: {dur}s, {len(words)} palabras, {nseg} escenas", flush=True)


if __name__ == "__main__":
    main()
