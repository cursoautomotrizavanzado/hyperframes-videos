#!/usr/bin/env node
// Une video mudo + voz (FFmpeg), incrusta la portada (attached_pic) y optimiza para redes.
// Uso: node render/finalize.js <muda.mp4> <voz.mp3> <final.mp4>
"use strict";
const { execFileSync } = require("child_process");
const path = require("path");
const [silent, voz, out] = process.argv.slice(2);
const run = (args) => { console.log("[final] ffmpeg", args.join(" ")); execFileSync("ffmpeg", args, { stdio: "inherit" }); };
const cover = path.join(path.dirname(out), "portada.jpg");
run(["-y", "-v", "error", "-ss", "0.10", "-i", silent, "-frames:v", "1", "-q:v", "2", cover]);
run(["-y", "-v", "error", "-i", silent, "-i", voz, "-i", cover,
  "-map", "0:v:0", "-map", "1:a:0", "-map", "2:v:0",
  "-c:v:0", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
  "-c:v:1", "mjpeg", "-disposition:v:1", "attached_pic",
  "-movflags", "+faststart", out]);
console.log("[final] MP4 listo:", out);
