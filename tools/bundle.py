#!/usr/bin/env python3
"""Empaqueta la carpeta cloud/ en web/cloud_bundle.js (lo usa la app Android/PWA
para auto-instalar el motor en el GitHub del usuario y para la vista previa)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOUD = os.path.join(ROOT, "cloud")
files = {}
for base, dirs, names in os.walk(CLOUD):
    dirs[:] = [d for d in dirs if d not in ("node_modules", "out")]
    for n in sorted(names):
        p = os.path.join(base, n)
        rel = os.path.relpath(p, CLOUD).replace(os.sep, "/")
        files[rel] = open(p, encoding="utf-8").read()
out = os.path.join(ROOT, "web", "cloud_bundle.js")
with open(out, "w", encoding="utf-8") as f:
    f.write("/* Generado por tools/bundle.py — no editar a mano */\n")
    f.write("window.CLOUD_FILES = " + json.dumps(files, ensure_ascii=False, indent=0) + ";\n")
print("OK", out, len(files), "archivos:", ", ".join(sorted(files)))
