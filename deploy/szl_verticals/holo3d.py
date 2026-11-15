"""SZL holo3d v1 - fully 3D holographic engine constellation.

Self-contained, server-rendered WebGL constellation for the vertical-services
front door. Doctrine: same-origin catalog feed only (/api/catalog), fails
closed when the chain is unreachable, honest labelling (procedural layout is
ILLUSTRATIVE and never claimed as measured topology), no persistence APIs, no
tracking, and no external assets of any kind. Leader patterns leveraged
(2026-11-15 sweep): spatial-hud instanced-particle GLSL, HOLO.SYS scanline
holographic shaders, Brain-Storm measured-vs-rendered honesty labelling.
"""
from __future__ import annotations

HOLO3D_CSS = """
/* holo3d v1 - front-door constellation mount (cosmetics; a11y included). */
#holo-fab{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));z-index:40;display:inline-flex;align-items:center;gap:8px;min-height:44px;min-width:44px;padding:10px 14px;border-radius:999px;border:1px solid var(--line,#2a3350);background:var(--panel,rgba(13,18,33,.86));color:var(--text,#e8ecf8);font:700 11px/1 ui-monospace,monospace;letter-spacing:.12em;cursor:pointer}
#holo-fab:hover,#holo-fab:focus-visible{border-color:var(--accent,#7df)}
#holo-panel{position:fixed;inset:3vh 3vw;z-index:50;display:none;flex-direction:column;background:rgba(5,8,16,.94);border:1px solid var(--line,#2a3350);border-radius:16px}
#holo-panel.open{display:flex}
#holo-panel header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;border-bottom:1px solid var(--line,#2a3350)}
#holo-panel h2{margin:0;font:700 12px/1.4 ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--accent,#7df)}
#holo-close{min-height:44px;min-width:44px;padding:6px 12px;border-radius:8px;border:1px solid var(--line,#2a3350);background:transparent;color:var(--text,#e8ecf8);font:700 11px/1 ui-monospace,monospace;cursor:pointer}
.holo-stage{position:relative;flex:1;min-height:0}
#holo-canvas{position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:none}
#holo-offline{position:absolute;top:14px;left:50%;transform:translateX(-50%);margin:0;color:var(--warn,#ffb36b);border:1px solid var(--warn,#ffb36b);border-radius:999px;padding:6px 14px;font:700 11px/1 ui-monospace,monospace;background:rgba(13,18,33,.9)}
#holo-hud{position:absolute;left:0;right:0;bottom:12px;display:flex;gap:8px;flex-wrap:wrap;justify-content:center;padding:0 12px;pointer-events:none}
.holo-chip{font:700 10.5px/1.6 ui-monospace,monospace;color:var(--muted,#a9b4d0);background:rgba(13,18,33,.72);border:1px solid var(--line,#2a3350);border-radius:999px;padding:4px 12px}
.holo-chip.ok{color:#9ef0c0}.holo-chip.off{color:#ffb36b}.holo-chip.note{color:#ffd166}
#holo-tip{position:absolute;opacity:0;pointer-events:none;background:#041018;color:#9ef0c0;border-radius:6px;padding:3px 8px;font:700 11px/1.4 ui-monospace,monospace;transform:translate(-50%,-160%)}
.holo-note{margin:0;padding:10px 16px;border-top:1px solid var(--line,#2a3350);color:var(--muted,#a9b4d0);font:12px/1.5 system-ui,sans-serif}
@media (max-width:640px){#holo-panel{inset:2vh 2vw}#holo-fab{padding:10px 12px}}
@media (prefers-reduced-motion: reduce){#holo-fab,#holo-panel,#holo-tip{transition:none;animation:none}}
@media (forced-colors: active){#holo-fab,#holo-panel,#holo-close{border:1px solid CanvasText}}
"""

HOLO3D_JS = """
/* holo3d v1 - catalog-honest WebGL constellation of the governed engines. */
(() => {
  "use strict";
  var FEED = "/api/catalog";
  var FAB_ID = "holo-fab";
  var PANEL_ID = "holo-panel";
  var CANVAS_ID = "holo-canvas";
  var TIP_ID = "holo-tip";
  var HUD_ID = "holo-hud";
  var OFFLINE_ID = "holo-offline";
  var REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var st = { open: false, built: false, building: false, gl: null, prog: null,
             posBuf: null, lineBuf: null, labels: [], proj: [],
             rotX: 0.18, rotY: 0, zoom: 2.1, drag: false, lx: 0, ly: 0,
             lastFocus: null, raf: 0, ro: null };

  function $(id) { return document.getElementById(id); }

  function chip(text, cls) {
    var hud = $(HUD_ID);
    if (!hud) { return; }
    var s = document.createElement("span");
    s.className = "holo-chip" + (cls ? " " + cls : "");
    s.textContent = text;
    hud.appendChild(s);
  }

  function collectNodes(payload) {
    var nodes = [];
    var raw = payload && payload.engines;
    var entries = [];
    if (Object.prototype.toString.call(raw) === "[object Array]") {
      for (var i = 0; i < raw.length; i++) {
        var e = raw[i];
        if (!e || typeof e !== "object") { continue; }
        entries.push({ label: e.name || e.alias || e.id || e.vertical || "engine", sub: e.models || e.kernels || e.capabilities || e.contracts || e.aliases });
      }
    } else if (raw && typeof raw === "object") {
      var keys = Object.keys(raw);
      for (var j = 0; j < keys.length; j++) {
        var v = raw[keys[j]];
        var sub = null;
        if (v && typeof v === "object") {
          sub = v.models || v.kernels || v.capabilities || v.contracts || v.aliases;
        }
        entries.push({ label: keys[j], sub: sub });
      }
    }
    for (var k = 0; k < entries.length && nodes.length < 96; k++) {
      var ent = entries[k];
      nodes.push(String(ent.label));
      var list = ent.sub;
      if (Object.prototype.toString.call(list) === "[object Array]") {
        for (var m = 0; m < list.length && m < 6 && nodes.length < 96; m++) {
          var item = list[m];
          var nm = item && typeof item === "object" ? (item.name || item.alias || item.id || item.state) : item;
          if (nm) { nodes.push(String(nm)); }
        }
      }
    }
    return nodes.slice(0, 96);
  }

  function fetchFeed() {
    return fetch(FEED, {
      headers: { accept: "application/json" },
      credentials: "same-origin",
      cache: "no-store"
    }).then(function (res) {
      if (!res.ok) { throw new Error("HTTP " + res.status); }
      return res.json();
    });
  }

  var VSH =
    "attribute vec3 aPos;" +
    "attribute float aSeed;" +
    "uniform float uTime;" +
    "uniform float uRotX;" +
    "uniform float uRotY;" +
    "uniform float uZoom;" +
    "uniform float uDpr;" +
    "varying float vSeed;" +
    "void main() {" +
    "  vSeed = aSeed;" +
    "  float cx = cos(uRotX); float sx = sin(uRotX);" +
    "  float cy = cos(uRotY); float sy = sin(uRotY);" +
    "  vec3 p = aPos;" +
    "  p = vec3(p.x, p.y * cx - p.z * sx, p.y * sx + p.z * cx);" +
    "  p = vec3(p.x * cy + p.z * sy, p.y, -p.x * sy + p.z * cy);" +
    "  gl_Position = vec4(p.x / uZoom, p.y / uZoom, 0.0, 1.0);" +
    "  float pulse = 0.75 + 0.25 * sin(uTime * 2.0 + aSeed * 6.2831);" +
    "  gl_PointSize = 1.9 * pulse * (5.6 / uZoom) * uDpr;" +
    "}";
  var FSH =
    "precision mediump float;" +
    "uniform float uTime;" +
    "varying float vSeed;" +
    "void main() {" +
    "  vec2 c = gl_PointCoord - 0.5;" +
    "  float d = length(c);" +
    "  float a = smoothstep(0.5, 0.04, d);" +
    "  float scan = 0.82 + 0.18 * sin(vSeed * 40.0 - uTime * 5.0);" +
    "  vec3 teal = vec3(0.35, 0.82, 1.0);" +
    "  vec3 gold = vec3(1.0, 0.82, 0.40);" +
    "  vec3 rose = vec3(1.0, 0.36, 0.56);" +
    "  vec3 col = vSeed < 0.5 ? mix(teal, gold, vSeed * 2.0) : mix(gold, rose, (vSeed - 0.5) * 2.0);" +
    "  float alpha = a * scan * (0.55 + 0.45 * sin(uTime * 1.7 + vSeed * 12.566));" +
    "  if (alpha < 0.015) { discard; }" +
    "  gl_FragColor = vec4(col, alpha);" +
    "}";

  function fib(i, n, r) {
    var phi = Math.acos(1 - 2 * (i + 0.5) / n);
    var th = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
    return [r * Math.sin(phi) * Math.cos(th), r * Math.cos(phi) * 0.72, r * Math.sin(phi) * Math.sin(th)];
  }

  function compile(gl, kind, src) {
    var sh = gl.createShader(kind);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) { throw new Error("shader"); }
    return sh;
  }

  function buildScene(labels) {
    var canvas = $(CANVAS_ID);
    if (!canvas) { throw new Error("canvas missing"); }
    var gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    if (!gl) { throw new Error("webgl unavailable"); }
    st.gl = gl;
    var prog = gl.createProgram();
    gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VSH));
    gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FSH));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { throw new Error("link"); }
    gl.useProgram(prog);
    st.prog = prog;
    var n = labels.length;
    var pos = new Float32Array(n * 4);
    st.labels = labels;
    st.proj = [];
    for (var i = 0; i < n; i++) {
      var p = fib(i, n, 1.0);
      pos[i * 4] = p[0]; pos[i * 4 + 1] = p[1]; pos[i * 4 + 2] = p[2];
      pos[i * 4 + 3] = (i % 97) / 97;
      st.proj.push([0, 0]);
    }
    var lp = [];
    for (var k = 0; k < n - 1; k++) {
      lp.push(pos[k * 4], pos[k * 4 + 1], pos[k * 4 + 2], pos[k * 4 + 3],
              pos[(k + 1) * 4], pos[(k + 1) * 4 + 1], pos[(k + 1) * 4 + 2], pos[(k + 1) * 4 + 3]);
    }
    st.posBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, st.posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.STATIC_DRAW);
    st.lineBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, st.lineBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(lp), gl.STATIC_DRAW);
    var aPos = gl.getAttribLocation(prog, "aPos");
    var aSeed = gl.getAttribLocation(prog, "aSeed");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 16, 0);
    gl.enableVertexAttribArray(aSeed);
    gl.vertexAttribPointer(aSeed, 1, gl.FLOAT, false, 16, 12);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.clearColor(0, 0, 0, 0);
  }

  function sizeRenderer() {
    var panel = $(PANEL_ID), canvas = $(CANVAS_ID);
    if (!panel || !canvas || !st.gl) { return; }
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.max(1, panel.clientWidth), h = Math.max(1, panel.clientHeight - 90);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    st.gl.viewport(0, 0, canvas.width, canvas.height);
    st.gl.uniform1f(st.gl.getUniformLocation(st.prog, "uDpr"), dpr);
  }

  function render(t) {
    if (!st.gl) { return; }
    var gl = st.gl;
    gl.useProgram(st.prog);
    render_body(gl, t);
  }


  function render_body(gl, t) {
    gl.uniform1f(gl.getUniformLocation(st.prog, "uTime"), t);
    gl.uniform1f(gl.getUniformLocation(st.prog, "uRotX"), st.rotX);
    gl.uniform1f(gl.getUniformLocation(st.prog, "uRotY"), st.rotY);
    gl.uniform1f(gl.getUniformLocation(st.prog, "uZoom"), st.zoom);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.bindBuffer(gl.ARRAY_BUFFER, st.posBuf);
    gl.drawArrays(gl.POINTS, 0, st.labels.length);
    gl.bindBuffer(gl.ARRAY_BUFFER, st.lineBuf);
    gl.drawArrays(gl.LINES, 0, Math.max(0, (st.labels.length - 1) * 2));
    updateProjection();
  }

  function updateProjection() {
    var canvas = $(CANVAS_ID);
    if (!canvas) { return; }
    var cx = Math.cos(st.rotX), sx = Math.sin(st.rotX);
    var cy = Math.cos(st.rotY), sy = Math.sin(st.rotY);
    for (var i = 0; i < st.labels.length; i++) {
      var p = fib(i, st.labels.length, 1.0);
      var y1 = p[1] * cx - p[2] * sx;
      var z1 = p[1] * sx + p[2] * cx;
      var x2 = p[0] * cy + z1 * sy;
      st.proj[i] = [((x2 / st.zoom) * 0.5 + 0.5) * canvas.clientWidth,
                    ((-y1 / st.zoom) * 0.5 + 0.5) * canvas.clientHeight];
    }
  }

  function frame(now) {
    if (!st.open || !st.gl) { return; }
    var t = now / 1000;
    if (!REDUCED && !st.drag) { st.rotY += 0.0022; }
    render(t);
    if (!REDUCED) { st.raf = requestAnimationFrame(frame); }
  }

  function build() {
    if (st.built || st.building) { return; }
    st.building = true;
    fetchFeed().then(function (payload) {
      var labels = collectNodes(payload);
      if (!labels.length) { throw new Error("no catalog nodes"); }
      buildScene(labels);
      st.built = true;
      sizeRenderer();
      chip("catalog nodes " + labels.length, "ok");
      chip("ILLUSTRATIVE LAYOUT - procedural, not measured", "note");
      render(0);
      if (!REDUCED) { st.raf = requestAnimationFrame(frame); }
    }).catch(function () {
      var off = $(OFFLINE_ID);
      if (off) { off.hidden = false; }
      chip("CATALOG UNREACHABLE - failing closed", "off");
    }).then(function () { st.building = false; });
  }

  function openPanel() {
    var panel = $(PANEL_ID);
    if (!panel) { return; }
    st.open = true;
    st.lastFocus = document.activeElement;
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    if (!st.built) { build(); } else { sizeRenderer(); render(0); if (!REDUCED) { st.raf = requestAnimationFrame(frame); } }
    var closeBtn = $("holo-close");
    if (closeBtn) { closeBtn.focus({ preventScroll: true }); }
  }

  function closePanel() {
    var panel = $(PANEL_ID);
    if (!panel) { return; }
    st.open = false;
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    if (st.raf) { cancelAnimationFrame(st.raf); st.raf = 0; }
    if (st.lastFocus && document.body.contains(st.lastFocus)) { st.lastFocus.focus({ preventScroll: true }); }
  }

  function wire() {
    var fab = $(FAB_ID), panel = $(PANEL_ID), canvas = $(CANVAS_ID);
    if (!fab || !panel || !canvas) { return; }
    fab.addEventListener("click", function () { if (st.open) { closePanel(); } else { openPanel(); } });
    $("holo-close").addEventListener("click", closePanel);
    panel.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { closePanel(); return; }
      if (e.key === "Tab") {
        var focusables = [$("holo-close"), $(CANVAS_ID)].filter(Boolean);
        var idx = focusables.indexOf(document.activeElement);
        e.preventDefault();
        var next = e.shiftKey ? focusables[(idx - 1 + focusables.length) % focusables.length] : focusables[(idx + 1) % focusables.length];
        if (next) { next.focus({ preventScroll: true }); }
      }
    });
    canvas.addEventListener("pointerdown", function (e) {
      st.drag = true; st.lx = e.clientX; st.ly = e.clientY;
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointerup", function (e) {
      st.drag = false;
      try { canvas.releasePointerCapture(e.pointerId); } catch (err) {}
    });
    canvas.addEventListener("pointermove", function (e) {
      if (st.drag) {
        st.rotY += (e.clientX - st.lx) * 0.006;
        st.rotX = Math.max(-1.2, Math.min(1.2, st.rotX + (e.clientY - st.ly) * 0.006));
        st.lx = e.clientX; st.ly = e.clientY;
        if (REDUCED) { render(0); }
      }
      var tip = $(TIP_ID);
      if (!tip || !st.proj.length) { return; }
      var rect = canvas.getBoundingClientRect();
      var best = -1, bestD = 16;
      for (var i = 0; i < st.proj.length; i++) {
        var dx = e.clientX - rect.left - st.proj[i][0];
        var dy = e.clientY - rect.top - st.proj[i][1];
        var d = Math.sqrt(dx * dx + dy * dy);
        if (d < bestD) { bestD = d; best = i; }
      }
      if (best >= 0) {
        tip.textContent = st.labels[best];
        tip.style.left = st.proj[best][0] + "px";
        tip.style.top = st.proj[best][1] + "px";
        tip.style.opacity = 1;
      } else { tip.style.opacity = 0; }
    });
    canvas.addEventListener("wheel", function (e) {
      e.preventDefault();
      st.zoom = Math.max(1.2, Math.min(6, st.zoom + e.deltaY * 0.0016));
      if (REDUCED) { render(0); }
    }, { passive: false });
    if (typeof ResizeObserver === "function") {
      st.ro = new ResizeObserver(function () { if (st.open) { sizeRenderer(); if (REDUCED) { render(0); } } });
      st.ro.observe(panel);
    } else {
      window.addEventListener("resize", function () { if (st.open) { sizeRenderer(); } });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire, { once: true });
  } else { wire(); }
})();
"""

HOLO3D_PANEL_HTML = """
<button id="holo-fab" type="button" aria-haspopup="dialog" aria-controls="holo-panel">3D HOLO</button>
<section id="holo-panel" role="dialog" aria-modal="true" aria-label="3D holographic engine constellation" aria-hidden="true">
<header><h2>Engine constellation</h2><button id="holo-close" type="button">Close (Esc)</button></header>
<div class="holo-stage">
<canvas id="holo-canvas" tabindex="0" aria-label="Interactive 3D holographic constellation of the governed engine catalog"></canvas>
<p id="holo-offline" hidden>CATALOG UNREACHABLE - failing closed</p>
<div id="holo-hud" role="status" aria-live="polite"></div>
<div id="holo-tip" aria-hidden="true"></div>
</div>
<p class="holo-note">ILLUSTRATIVE LAYOUT - node positions are procedural, never a measured topology. Catalog labels only; no candidate text crosses this surface.</p>
</section>
"""
