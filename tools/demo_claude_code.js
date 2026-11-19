window.renderEscena = function (ctx, info) {
  var L = info.lib, P = info.P, R = info.R, u = info.u, lc = info.local, t = info.t;
  var X = function (f) { return R.x + R.w * f; }, Y = function (f) { return R.y + R.h * f; };
  function seg(a, b, col, w) { ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = "round"; ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }
  function coil(cx, cy, w, h, turns, col, lw, prog, phase) {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = lw; ctx.lineCap = "round";
    var n = Math.floor(turns * L.clamp(prog, 0, 1));
    for (var k = 0; k < n; k++) { var y = cy - h / 2 + h * (k + 0.5) / turns; ctx.beginPath(); ctx.ellipse(cx, y, w / 2, Math.max(3, h / turns * 0.42), 0, phase || 0, Math.PI * 2); ctx.stroke(); }
    ctx.restore();
  }
  function leader(x1, y1, x2, y2, txt, col, a, tx, ty, al) { if (a <= 0) return; ctx.save(); ctx.globalAlpha *= a; seg([x1, y1], [x2, y2], col, 3); L.label(txt, tx, ty, col, 28 * u, al, 800); ctx.restore(); }
  function axes(gx, gy, gw, gh, yl, xl) {
    ctx.strokeStyle = "rgba(185,204,240,.7)"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(gx, gy + gh); ctx.lineTo(gx + gw, gy + gh); ctx.stroke();
    L.label(yl, gx + 8, gy - 22, P.dim, 22 * u, "left", 700); L.label(xl, gx + gw, gy + gh + 30, P.dim, 22 * u, "right", 700);
  }
  function ramp(gx, gy, gw, gh, prog, tau, col, sat) {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 6; ctx.shadowColor = col; ctx.shadowBlur = 10; ctx.beginPath();
    var n = Math.max(2, Math.floor(80 * L.clamp(prog, 0, 1)));
    for (var k = 0; k <= n; k++) { var x = k / 80, v = Math.min(sat, 1 - Math.exp(-x / tau)) / 1.0; var px = gx + gw * x, py = gy + gh - gh * 0.85 * v / sat * sat; if (k) ctx.lineTo(px, py); else ctx.moveTo(px, py); }
    ctx.stroke(); ctx.restore();
  }
  switch (info.i) {
    case 0: {
      var cx = X(0.5), cy = Y(0.48), core = L.easeOut(lc / 0.6);
      ctx.save(); ctx.globalAlpha *= core; L.rr(cx - 34 * u, Y(0.08), 68 * u, R.h * 0.8, 10); ctx.fillStyle = "#3E4C66"; ctx.fill(); ctx.strokeStyle = "#8EA3C8"; ctx.lineWidth = 3; ctx.stroke();
      for (var k = 1; k < 10; k++) { ctx.fillStyle = "rgba(255,255,255,.06)"; ctx.fillRect(cx - 34 * u, Y(0.08) + R.h * 0.08 * k, 68 * u, 3); } ctx.restore();
      coil(cx, cy, 150 * u, R.h * 0.42, 7, P.amber, 12 * u, L.easeOut(info.since("primario") / 0.9));
      coil(cx, cy, 300 * u, R.h * 0.7, 46, P.cyan, 3, L.easeOut(info.since("secundario") / 1.2));
      leader(cx - 70 * u, Y(0.6), X(0.18), Y(0.8), "PRIMARIO", P.amber, L.easeOut(info.since("primario") / 0.4), X(0.03), Y(0.85), "left");
      leader(cx + 150 * u, Y(0.3), X(0.82), Y(0.14), "SECUNDARIO", P.cyan, L.easeOut(info.since("secundario") / 0.4), X(0.97), Y(0.09), "right");
      leader(cx + 34 * u, Y(0.88), X(0.7), Y(0.96), "NÚCLEO", P.white, L.easeOut(info.since("núcleo") / 0.4), X(0.72), Y(0.96), "left");
      break;
    }
    case 1: {
      var bx = X(0.04), top = Y(0.12), bot = Y(0.86), cx2 = X(0.24), on = info.since("masa") > 0;
      L.box(bx, top, 120 * u, 70 * u, P.red, 1); L.label("+12 V", bx + 60 * u, top + 35 * u, P.red, 28 * u, "center", 800);
      var path = [[bx + 120 * u, top + 35 * u], [cx2, top + 35 * u], [cx2, Y(0.3)]];
      L.stroke(path, P.red, 6, 1);
      coil(cx2, Y(0.42), 90 * u, R.h * 0.22, 6, P.amber, 9 * u, 1);
      var p2 = [[cx2, Y(0.53)], [cx2, Y(0.64)]]; L.stroke(p2, P.amber, 6, 1);
      L.box(cx2 - 75 * u, Y(0.64), 150 * u, 80 * u, P.yellow || P.amber, 1); L.label("MÓDULO", cx2, Y(0.64) + 28 * u, P.white, 24 * u, "center", 800); L.label(on ? "A MASA" : "ABIERTO", cx2, Y(0.64) + 56 * u, on ? P.green : P.dim, 22 * u, "center", 800);
      L.stroke([[cx2, Y(0.64) + 80 * u], [cx2, bot]], P.green, 6, 1);
      ctx.strokeStyle = P.green; ctx.lineWidth = 5; for (var g = 0; g < 3; g++) seg([cx2 - (30 - g * 10) * u, bot + g * 12 * u], [cx2 + (30 - g * 10) * u, bot + g * 12 * u], P.green, 5);
      if (on) { L.flowDots(path.concat([[cx2, Y(0.53)], [cx2, bot]]), P.cyan, t, 120, 40, 6, 1); }
      var gx = X(0.5), gy = Y(0.12), gw = R.w * 0.46, gh = R.h * 0.66;
      axes(gx, gy, gw, gh, "CORRIENTE (A)", "TIEMPO (ms)");
      var pr = L.easeOut(info.since("rampa") / 1.4); if (pr > 0) ramp(gx, gy, gw, gh, pr, 0.45, P.cyan, 1);
      var lim = L.easeOut(info.since("siete") / 0.4);
      if (lim > 0) { ctx.save(); ctx.globalAlpha *= lim; ctx.setLineDash([12, 10]); seg([gx, gy + gh - gh * 0.85 * 0.9], [gx + gw, gy + gh - gh * 0.85 * 0.9], P.amber, 3); ctx.setLineDash([]); L.label("≈ 7 A", gx + gw - 10, gy + gh - gh * 0.85 * 0.9 - 26, P.amber, 34 * u, "right", 800); ctx.restore(); }
      break;
    }
    case 2: {
      var kx = X(0.27), ky = Y(0.48), col = info.since("colapsa"), shrink = col > 0 ? Math.max(0, 1 - col / 0.8) : 1;
      for (var f = 0; f < 4; f++) { ctx.save(); ctx.globalAlpha *= 0.25 + 0.15 * f; ctx.strokeStyle = P.blue; ctx.lineWidth = 3; ctx.setLineDash([10, 8]); ctx.lineDashOffset = -t * 30;
        ctx.beginPath(); ctx.ellipse(kx, ky, (90 + f * 45) * u * shrink + 1, R.h * (0.18 + f * 0.07) * shrink + 1, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); }
      L.rr(kx - 26 * u, Y(0.18), 52 * u, R.h * 0.6, 8); ctx.fillStyle = "#3E4C66"; ctx.fill();
      coil(kx, ky, 110 * u, R.h * 0.3, 6, P.amber, 9 * u, 1); coil(kx, ky, 200 * u, R.h * 0.5, 30, P.cyan, 3, 1);
      var px = X(0.74), py = Y(0.1), sp = info.since("chispa");
      L.rr(px - 22 * u, py, 44 * u, R.h * 0.36, 14); ctx.fillStyle = "#EDEFF3"; ctx.fill();
      L.rr(px - 34 * u, py + R.h * 0.36, 68 * u, R.h * 0.2, 6); ctx.fillStyle = "#9AA7BD"; ctx.fill();
      for (var th = 0; th < 5; th++) seg([px - 34 * u, py + R.h * (0.38 + th * 0.035)], [px + 34 * u, py + R.h * (0.39 + th * 0.035)], "#6C7A93", 3);
      var ey = py + R.h * 0.62; seg([px, py + R.h * 0.56], [px, ey], "#C9D2E3", 8); seg([px + 30 * u, py + R.h * 0.56], [px + 30 * u, ey + 30 * u], "#C9D2E3", 8); seg([px + 30 * u, ey + 30 * u], [px + 4, ey + 30 * u], "#C9D2E3", 8);
      if (sp > 0) { var fl = 0.6 + 0.4 * Math.abs(Math.sin(t * 37)); ctx.save(); ctx.globalAlpha *= fl;
        var gl = ctx.createRadialGradient(px + 15 * u, ey + 16 * u, 2, px + 15 * u, ey + 16 * u, 70 * u); gl.addColorStop(0, "rgba(160,240,255,.9)"); gl.addColorStop(1, "rgba(0,229,255,0)"); ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(px + 15 * u, ey + 16 * u, 70 * u, 0, 7); ctx.fill();
        ctx.strokeStyle = "#FFFFFF"; ctx.shadowColor = P.cyan; ctx.shadowBlur = 30; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(px + 2, ey + 2);
        for (var z = 1; z <= 4; z++) ctx.lineTo(px + 2 + (z % 2 ? 14 : -4) * u + Math.sin(t * 50 + z) * 3, ey + 2 + z * 7 * u); ctx.stroke(); ctx.restore();
        L.label("¡CHISPA!", px + 15 * u, ey + 90 * u, P.white, 32 * u, "center", 800); }
      var kv = L.easeOut(info.since("miles") / 0.8);
      if (kv > 0) { ctx.save(); ctx.globalAlpha *= kv; L.label(Math.round(30 * kv) + " kV", X(0.74), Y(1.0), P.red, 52 * u, "center", 800, true); ctx.restore(); }
      break;
    }
    case 3: {
      var gx3 = X(0.1), gy3 = Y(0.1), gw3 = R.w * 0.8, gh3 = R.h * 0.7;
      axes(gx3, gy3, gw3, gh3, "CORRIENTE (A)", "TIEMPO (ms)");
      ramp(gx3, gy3, gw3, gh3, L.easeOut(lc / 1.2), 0.45, P.green, 1);
      L.label("NORMAL", gx3 + gw3 * 0.72, gy3 + gh3 * 0.42, P.green, 30 * u, "center", 800);
      var bad = L.easeOut(info.since("rápido") / 0.7);
      if (bad > 0) { ramp(gx3, gy3, gw3, gh3, bad, 0.12, P.red, 1); ctx.save(); ctx.globalAlpha *= bad; L.label("EN CORTO", gx3 + gw3 * 0.2, gy3 + gh3 * 0.32, P.red, 32 * u, "left", 800); ctx.restore(); }
      break;
    }
    default: return false;
  }
};
