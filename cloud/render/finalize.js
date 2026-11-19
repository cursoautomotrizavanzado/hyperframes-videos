#!/usr/bin/env node
// Une video mudo + voz (FFmpeg), incrusta la portada (attached_pic) y optimiza para redes.
// Uso: node render/finalize.js <muda.mp4> <voz.mp3> <final.mp4> [efectos.wav]
"use strict";
const { execFileSync } = require("child_process");
const path = require("path");
const [silent, voz, out, sfx] = process.argv.slice(2);
const fs = require("fs");
const run = (args) => { console.log("[final] ffmpeg", args.join(" ")); execFileSync("ffmpeg", args, { stdio: "inherit" }); };
const cover = path.join(path.dirname(out), "portada.jpg");
run(["-y", "-v", "error", "-ss", "0.10", "-i", silent, "-frames:v", "1", "-q:v", "2", cover]);
const SFX_DB = process.env.SFX_DB || "-18";
const hasSfx = sfx && fs.existsSync(sfx);
const args = ["-y", "-v", "error", "-i", silent, "-i", voz, "-i", cover];
if (hasSfx) args.push("-i", sfx);
if (hasSfx) {
  // efectos a -18 dB bajo la voz (la voz ya viene normalizada a -16 LUFS)
  args.push("-filter_complex", `[3:a]volume=${SFX_DB}dB,aresample=48000[s];[1:a]aresample=48000[v];[v][s]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]`,
    "-map", "0:v:0", "-map", "[a]", "-map", "2:v:0");
} else args.push("-map", "0:v:0", "-map", "1:a:0", "-map", "2:v:0");
args.push("-c:v:0", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-c:v:1", "mjpeg", "-disposition:v:1", "attached_pic", "-movflags", "+faststart", out);
run(args);
console.log("[final] MP4 listo:", out, hasSfx ? "(con efectos de sonido)" : "");
