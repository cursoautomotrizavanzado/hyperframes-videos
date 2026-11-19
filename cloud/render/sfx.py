#!/usr/bin/env python3
"""Diseño sonoro sintetizado (sin bancos de sonido): pop, tick, alerta, whoosh, chime, impacto, zumbido.
Uso: python3 render/sfx.py <events.json> <salida.wav>"""
import json, math, random, struct, sys, wave

SR = 44100


def env_exp(n, tau):
    return [math.exp(-i / (tau * SR)) for i in range(n)]


def pop():
    n = int(0.09 * SR); e = env_exp(n, 0.025); out = []
    ph = 0.0
    for i in range(n):
        f = 700 + 900 * (i / n); ph += 2 * math.pi * f / SR
        out.append(0.9 * math.sin(ph) * e[i] * min(1, i / 60))
    return out


def tick():
    n = int(0.03 * SR); e = env_exp(n, 0.006)
    return [0.8 * math.sin(2 * math.pi * 2400 * i / SR) * e[i] for i in range(n)]


def alerta():
    out = []
    for f in (880, 660):
        n = int(0.13 * SR)
        for i in range(n):
            a = min(1, i / 200) * min(1, (n - i) / 400)
            out.append(0.55 * (1 if math.sin(2 * math.pi * f * i / SR) > 0 else -1) * a * 0.6)
        out += [0.0] * int(0.03 * SR)
    return out


def whoosh(seed=1):
    rnd = random.Random(seed); n = int(0.42 * SR); out = []; y = 0.0
    for i in range(n):
        x = i / n; a = math.sin(math.pi * x) ** 2
        k = 0.02 + 0.25 * x  # filtro que se abre
        y += k * (rnd.uniform(-1, 1) - y)
        out.append(1.6 * y * a)
    return out


def chime():
    n = int(1.4 * SR); out = []
    for i in range(n):
        tt = i / SR; v = 0.0
        for j, f in enumerate((1046.5, 1318.5, 1568.0)):
            d = max(0, tt - j * 0.07)
            if tt >= j * 0.07:
                v += math.sin(2 * math.pi * f * d) * math.exp(-d / 0.45)
        out.append(0.32 * v)
    return out


def impacto():
    n = int(0.45 * SR); out = []; ph = 0.0
    for i in range(n):
        f = 110 * math.exp(-i / (0.12 * SR)) + 42; ph += 2 * math.pi * f / SR
        out.append(0.95 * math.sin(ph) * math.exp(-i / (0.16 * SR)))
    return out


def zumbido():
    n = int(0.6 * SR)
    return [0.35 * (math.sin(2 * math.pi * 120 * i / SR) + 0.4 * math.sin(2 * math.pi * 240 * i / SR)) * min(1, i / 2000) * min(1, (n - i) / 4000) for i in range(n)]


BANK = {"pop": pop(), "tick": tick(), "alerta": alerta(), "whoosh": whoosh(), "chime": chime(), "impacto": impacto(), "zumbido": zumbido()}


def main():
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    dur = float(data.get("duration", 10)) + 1.5
    buf = [0.0] * int(dur * SR)
    for ev in data.get("events", []):
        s = BANK.get(ev.get("tipo"), BANK["pop"]); o = int(float(ev["t"]) * SR)
        for i, v in enumerate(s):
            if 0 <= o + i < len(buf):
                buf[o + i] += v
    peak = max(1e-6, max(abs(v) for v in buf))
    g = 0.89 / peak if peak > 0.89 else 1.0
    with wave.open(sys.argv[2], "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v * g)) * 32767)) for v in buf))
    print(f"[sfx] {len(data.get('events', []))} efectos sintetizados -> {sys.argv[2]}")


if __name__ == "__main__":
    main()
