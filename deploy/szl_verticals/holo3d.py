"""SZL holo3d v2 - fully 3D holographic engine constellation and vertical frontier scene.

Server-rendered holographic scene for the vertical-services front door. The
renderer is the shared three.js r170 WebGPU engine (MIT, vendored byte-for-byte
from a11oy, pinned by size and sha256, served same-origin, re-hashed in the
browser before it is imported) whose own WebGL2 backend covers browsers without
WebGPU; if the engine is missing or fails its integrity check the original
raw-WebGL renderer takes over and the HUD says so.
v1 (the engine constellation) is unchanged in doctrine: same-origin catalog
feed (/api/catalog), fails closed when the feed is unreachable, procedural
layout labelled ILLUSTRATIVE, no persistence APIs, no tracking, no external
assets of any kind except that one pinned, hash-verified engine file.

v2 adds one more same-origin read-only feed, /api/verticals/{vertical}/frontier,
and renders the real server payload for each of the six verticals:

* the nine Living Anatomy organs as knots on a khipu cord (the cord frays from
  the first organ whose reported readiness requirement is unmet);
* every bound formula, with its material taken from the status string the
  server reports (the exact string is always shown as text);
* every official-source connector as a labelled gap when it has no reading in
  scope or its state is not READY (for example AUTH_REQUIRED);
* the advisory Lambda roll-up, recomputed in the browser as a weighted
  geometric mean and compared with the server score.

The renderer never upgrades a label (REPORTED stays REPORTED) and never invents
data. Positions are seeded from the build revision digest and are labelled
ILLUSTRATIVE LAYOUT, never a measured topology. Design:
docs/2026-11-19-vertical-holo-v2-design.md. Leader patterns leveraged
(2026-11-15 sweep): spatial-hud instanced-particle GLSL, HOLO.SYS scanline
holographic shaders, Brain-Storm measured-vs-rendered honesty labelling.
"""
from __future__ import annotations

HOLO3D_CSS = """
/* holo3d v2 - front-door constellation and vertical frontier mount (cosmetics; a11y included). */
#holo-fab{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));z-index:40;display:inline-flex;align-items:center;gap:8px;min-height:44px;min-width:44px;padding:10px 14px;border-radius:999px;border:1px solid var(--line,#2a3350);background:var(--panel,rgba(13,18,33,.86));color:var(--text,#e8ecf8);font:700 11px/1 ui-monospace,monospace;letter-spacing:.12em;cursor:pointer}
#holo-fab:hover,#holo-fab:focus-visible{border-color:var(--accent,#7df)}
#holo-panel{position:fixed;inset:3vh 3vw;z-index:50;display:none;flex-direction:column;background:rgba(5,8,16,.97);border:1px solid var(--line,#2a3350);border-radius:16px}
#holo-panel.open{display:flex}
#holo-panel header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;border-bottom:1px solid var(--line,#2a3350)}
#holo-panel h2{margin:0;font:700 12px/1.4 ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--accent,#7df)}
#holo-close{min-height:44px;min-width:44px;padding:6px 12px;border-radius:8px;border:1px solid var(--line,#2a3350);background:transparent;color:var(--text,#e8ecf8);font:700 11px/1 ui-monospace,monospace;cursor:pointer}
.holo-stage{position:relative;flex:1;min-height:0}
#holo-canvas{position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:none}
#holo-offline{position:absolute;top:14px;left:50%;transform:translateX(-50%);margin:0;color:var(--warn,#ffb36b);border:1px solid var(--warn,#ffb36b);border-radius:999px;padding:6px 14px;font:700 11px/1 ui-monospace,monospace;background:rgba(13,18,33,.9)}
#holo-hud{position:absolute;left:10px;top:10px;bottom:auto;display:flex;flex-direction:column;align-items:flex-start;gap:5px;max-width:min(46%,520px);max-height:calc(100% - 20px);overflow:auto;padding:0;pointer-events:none}
.holo-chip{white-space:normal;font:700 10.5px/1.45 ui-monospace,monospace;color:var(--muted,#a9b4d0);background:rgba(13,18,33,.72);border:1px solid var(--line,#2a3350);border-radius:10px;padding:3px 10px}
.holo-chip.ok{color:#9ef0c0}.holo-chip.off{color:#ffb36b}.holo-chip.note{color:#ffd166}
#holo-canvas3d{position:absolute;inset:0;width:100%;height:100%;display:block;pointer-events:none}
#holo-tip{position:absolute;opacity:0;pointer-events:none;background:#041018;color:#9ef0c0;border-radius:6px;padding:3px 8px;font:700 11px/1.4 ui-monospace,monospace;transform:translate(-50%,-160%)}
.holo-note{margin:0;padding:10px 16px;border-top:1px solid var(--line,#2a3350);color:var(--muted,#a9b4d0);font:12px/1.5 system-ui,sans-serif}
#holo-views{display:flex;flex-wrap:wrap;gap:6px;padding:8px 16px;border-bottom:1px solid var(--line,#2a3350)}
#holo-views button{min-height:44px;min-width:44px;padding:6px 12px;border-radius:999px;border:1px solid var(--line,#2a3350);background:transparent;color:var(--text,#e8ecf8);font:700 11px/1 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
#holo-views button[aria-pressed="true"]{border-color:var(--accent,#7df);color:var(--accent,#7df)}
#holo-views button:focus-visible{outline:2px solid var(--accent,#7df);outline-offset:2px}
#holo-details{border-top:1px solid var(--line,#2a3350);padding:6px 16px;color:var(--muted,#a9b4d0);font:12px/1.5 system-ui,sans-serif}
#holo-details summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font:700 11px/1 ui-monospace,monospace;letter-spacing:.1em}
#holo-readout{margin:0 0 8px;padding-left:18px;max-height:24vh;overflow:auto}
@media (max-width:640px){#holo-hud{left:0;right:0;top:auto;bottom:6px;flex-direction:row;flex-wrap:wrap;justify-content:center;max-width:none;max-height:45%;padding:0 8px}#holo-panel{inset:2vh 2vw}#holo-fab{padding:10px 12px}}
@media (prefers-reduced-motion: reduce){#holo-fab,#holo-panel,#holo-tip{transition:none;animation:none}}
@media (forced-colors: active){#holo-fab,#holo-panel,#holo-close,#holo-views button{border:1px solid CanvasText}#holo-views button[aria-pressed="true"]{border-width:3px}}
"""

HOLO3D_JS = """
/* holo3d v2 - catalog-honest constellation plus data-bound vertical frontier scene. */
(() => {
  "use strict";
  var FEED = "/api/catalog";
  var FAB_ID = "holo-fab";
  var PANEL_ID = "holo-panel";
  var CANVAS_ID = "holo-canvas";
  var TIP_ID = "holo-tip";
  var HUD_ID = "holo-hud";
  var OFFLINE_ID = "holo-offline";
  var VIEWS_ID = "holo-views";
  var READOUT_ID = "holo-readout";
  var TITLE_ID = "holo-title";
  var REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var st = { open: false, ready: false, gl: null, prog: null, loc: null,
             posBuf: null, lineBuf: null, nodes: [], lineCount: 0, proj: [],
             view: "engines", seq: 0, fetchedAt: 0, glow: 1,
             rotX: 0.18, rotY: 0, zoom: 2.1, drag: false, lx: 0, ly: 0,
             lastFocus: null, raf: 0, ro: null, tick: 0, mode: "", rp: null, why: "" };

  function $(id) { return document.getElementById(id); }

  function chip(text, cls) {
    var hud = $(HUD_ID);
    if (!hud) { return; }
    var s = document.createElement("span");
    s.className = "holo-chip" + (cls ? " " + cls : "");
    s.textContent = text;
    hud.appendChild(s);
    return s;
  }

  function clearHud() {
    var hud = $(HUD_ID);
    while (hud && hud.firstChild) { hud.removeChild(hud.firstChild); }
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

  function fetchFrontier(key) {
    return fetch("/api/verticals/" + encodeURIComponent(key) + "/frontier", {
      headers: { accept: "application/json" },
      credentials: "same-origin",
      cache: "no-store"
    }).then(function (res) {
      if (!res.ok) { throw new Error("HTTP " + res.status); }
      return res.json();
    });
  }

  /* V2-MODEL-BEGIN (pure functions; exercised by the node contract test) */
  var VERTICALS = ["finance", "terra", "counsel", "lyte", "killinchu", "sentra"];
  var K = { SOLID: 0, WIRE: 1, POINTS: 2, OUTLINE: 3, GAP: 4, REPORTED: 5, CORE: 6,
            LINE: 10, CORD: 11, FRAYED: 12 };
  var KIND_NAME = ["SOLID", "WIREFRAME", "POINTS", "OUTLINE", "GAP", "REPORTED-RING", "CORE"];
  var LABEL_KIND = { MEASURED: 0, MODELED: 1, SAMPLE: 2, ROADMAP: 3, UNAVAILABLE: 4, REPORTED: 5 };
  var STATUS_KIND = {
    TESTED_IMPLEMENTATION: 0, TESTED_TRANSFORM: 0, DETERMINISTIC_IMPLEMENTATION: 0,
    MODELED: 1, MODELED_ADVISORY: 1,
    ADVISORY: 3, ADVISORY_THRESHOLD: 3, POLICY_PARAMETER: 3
  };
  var REQ_ORGAN = {
    required_connector_contracts_ready: "sense",
    source_bound: "context",
    formula_registry_bound: "formula",
    observation_store_writable: "remember",
    persistent_signing_key: "receipt"
  };
  var AGE_FULL_S = 600;

  function clean(v, n) {
    var s = String(v == null ? "" : v), out = "";
    for (var i = 0; i < s.length && out.length < (n || 64); i++) {
      var c = s.charCodeAt(i);
      var hidden = c < 32 || c === 127 || (c >= 128 && c <= 159) || (c >= 0x200b && c <= 0x200f) ||
                   (c >= 0x2028 && c <= 0x202e) || (c >= 0x2066 && c <= 0x2069) || c === 0xfeff || (c >= 0xd800 && c <= 0xdfff);
      out += hidden ? " " : s.charAt(i);
    }
    return out;
  }

  function validRevision(v) {
    var s = clean(v, 64);
    if (s.length < 7) { return ""; }
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      if (!((c >= 48 && c <= 57) || (c >= 97 && c <= 102))) { return ""; }
    }
    return s;
  }

  function isArr(a) { return Object.prototype.toString.call(a) === "[object Array]"; }
  function own(o, k) { return !!o && typeof o === "object" && Object.prototype.hasOwnProperty.call(o, k); }

  function fnv(str) {
    var h = 2166136261;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = (h * 16777619) >>> 0;
    }
    return h / 4294967296;
  }

  function kindForLabel(label) {
    var key = clean(label, 24);
    return own(LABEL_KIND, key) ? LABEL_KIND[key] : K.OUTLINE;
  }

  function kindForStatus(status) {
    var key = clean(status, 40);
    return own(STATUS_KIND, key) ? STATUS_KIND[key] : K.OUTLINE;
  }

  function lambdaCheck(axes, weights, serverScore) {
    if (!axes || typeof axes !== "object" || !weights || typeof weights !== "object") { return null; }
    var keys = Object.keys(axes), wsum = 0, i;
    if (!keys.length) { return null; }
    for (i = 0; i < keys.length; i++) {
      var w = Number(weights[keys[i]]);
      if (!isFinite(w) || w < 0) { return null; }
      wsum += w;
    }
    if (!(wsum > 0)) { return null; }
    var logSum = 0, zero = false;
    for (i = 0; i < keys.length; i++) {
      var x = Number(axes[keys[i]]), wi = Number(weights[keys[i]]) / wsum;
      if (!isFinite(x) || x < 0 || x > 1) { return null; }
      if (x === 0 && wi > 0) { zero = true; } else if (wi > 0) { logSum += wi * Math.log(x); }
    }
    var local = zero ? 0 : Math.exp(logSum);
    var s = Number(serverScore);
    return { local: local, server: s, agrees: isFinite(s) && Math.abs(local - s) < 0.00002,
             weightsNormalised: Math.abs(wsum - 1) < 1e-9 };
  }

  function place(seedBase, id, ang, rad, y) {
    var ja = (fnv(seedBase + "|" + id + "|a") - 0.5) * 0.16;
    var jr = (fnv(seedBase + "|" + id + "|r") - 0.5) * 0.10;
    var jy = (fnv(seedBase + "|" + id + "|y") - 0.5) * 0.10;
    var a = ang + ja, r = rad + jr;
    return [r * Math.cos(a), y + jy, r * Math.sin(a)];
  }

  function buildVerticalScene(payload, key, fetchedAtMs) {
    if (!payload || typeof payload !== "object") { return null; }
    var schema = clean(payload.schema, 48);
    if (schema.indexOf("szl.vertical-frontier/") !== 0) { return null; }
    var vname = clean(payload.vertical, 24);
    if (!vname || (vname !== key && clean(payload.requested_vertical, 24) !== key)) { return null; }
    var anatomy = payload.anatomy && typeof payload.anatomy === "object" ? payload.anatomy : {};
    var organs = isArr(anatomy.organs) ? anatomy.organs.slice(0, 12) : [];
    var formulas = isArr(payload.formulas) ? payload.formulas.slice(0, 24) : [];
    var connectors = isArr(payload.connectors) ? payload.connectors.slice(0, 24) : [];
    var ready = payload.readiness && typeof payload.readiness === "object" ? payload.readiness : null;
    var rev = payload.source && typeof payload.source === "object" ? validRevision(payload.source.source_revision) : "";
    var seedBase = (rev || "NOREV") + "|" + vname;
    var nodes = [], lines = [], readout = [], chips = [], gaps = 0, TAU = Math.PI * 2, i;

    function add(label, pos, kind, val, text, group) {
      nodes.push({ label: clean(label, 60), pos: pos, kind: kind, val: val == null ? 1 : val,
                   seed: fnv(seedBase + "|" + label), text: clean(text, 220), group: group });
      return nodes.length - 1;
    }

    var product = clean(payload.product || vname, 40);
    var core = add(product, [0, 0, 0], K.CORE, 1, "vertical core | " + clean(payload.domain, 80), "core");

    var unmet = {};
    var reqs = ready && ready.requirements && typeof ready.requirements === "object" ? ready.requirements : null;
    if (reqs) {
      Object.keys(REQ_ORGAN).forEach(function (rk) {
        if (own(reqs, rk) && reqs[rk] !== true) { unmet[REQ_ORGAN[rk]] = rk; }
      });
    }
    var anatLabel = clean(anatomy.truth_label, 24);
    var organIdx = [];
    var frayFrom = -1;
    for (i = 0; i < organs.length; i++) {
      var og = organs[i] && typeof organs[i] === "object" ? organs[i] : {};
      var oid = clean(og.id || ("organ" + (i + 1)), 24);
      var okind = anatLabel ? kindForLabel(anatLabel) : K.OUTLINE;
      var why = "";
      if (own(unmet, oid)) { okind = K.GAP; why = " | GAP reason: requirement " + unmet[oid] + " not met"; if (frayFrom < 0) { frayFrom = i; } }
      var pos = place(seedBase, "organ:" + oid, (i / Math.max(1, organs.length)) * TAU, 0.55, 0.62 - i * (1.24 / Math.max(1, organs.length - 1)));
      organIdx.push(add("organ " + (i + 1) + ": " + oid, pos, okind, 1,
        clean(og.contract, 120) + " | anatomy label " + (anatLabel || "NONE") + why, "organ"));
    }
    for (i = 0; i + 1 < organIdx.length; i++) {
      lines.push({ a: nodes[organIdx[i]].pos, b: nodes[organIdx[i + 1]].pos,
                   kind: (frayFrom >= 0 && i >= frayFrom) ? K.FRAYED : K.CORD, seed: nodes[organIdx[i + 1]].seed });
    }
    if (frayFrom >= 0 && frayFrom === organIdx.length - 1) {
      var lastNode = nodes[organIdx[frayFrom]];
      lines.push({ a: lastNode.pos, b: [lastNode.pos[0], lastNode.pos[1] - 0.2, lastNode.pos[2]], kind: K.FRAYED, seed: lastNode.seed });
    }

    for (i = 0; i < formulas.length; i++) {
      var f = formulas[i] && typeof formulas[i] === "object" ? formulas[i] : {};
      var fid = clean(f.id || ("formula" + i), 48);
      var fstatus = clean(f.status, 40);
      var fk = kindForStatus(fstatus);
      var known = own(STATUS_KIND, fstatus);
      var fi = add(fid, place(seedBase, "formula:" + fid, (i / Math.max(1, formulas.length)) * TAU, 1.0, -0.05),
        fk, 1, clean(f.name, 50) + " | " + clean(f.equation, 70) + " | status " + (fstatus || "NONE") +
        (known ? "" : " (UNRECOGNISED STATUS, shown as outline)") +
        (f.proof_boundary ? " | boundary: " + clean(f.proof_boundary, 100) : ""), "formula");
      lines.push({ a: nodes[core].pos, b: nodes[fi].pos, kind: K.LINE, seed: nodes[fi].seed });
    }

    var live = ready && ready.live_data && typeof ready.live_data === "object" ? ready.live_data : null;
    var observedN = live && isFinite(Number(live.connectors_observed)) ? Number(live.connectors_observed) : null;
    for (i = 0; i < connectors.length; i++) {
      var c = connectors[i] && typeof connectors[i] === "object" ? connectors[i] : {};
      var cid = clean(c.id || ("connector" + i), 48);
      var cstate = clean(c.state, 32) || "UNKNOWN";
      var reason, ck;
      if (cstate !== "READY") { reason = cstate.toLowerCase(); ck = K.GAP; }
      else if (observedN === 0 || observedN === null) { reason = "no_reading_in_scope"; ck = K.GAP; }
      else { reason = "reading_not_attributed_per_connector"; ck = K.OUTLINE; }
      if (ck === K.GAP) { gaps++; }
      var cpos = place(seedBase, "connector:" + cid, ((i + 0.5) / Math.max(1, connectors.length)) * TAU, 1.35, 0.4);
      var ci = add(cid, cpos, ck, 1, clean(c.authority, 60) + " | contract state " + cstate + " | " +
        (ck === K.GAP ? "GAP reason: " : "note: ") + reason + " | freshness window " + clean(c.freshness_seconds, 8) + "s", "connector");
      lines.push({ a: nodes[core].pos, b: nodes[ci].pos, kind: K.LINE, seed: nodes[ci].seed });
    }

    var lam = ready && ready.lambda_advisory && typeof ready.lambda_advisory === "object" ? ready.lambda_advisory : null;
    var lc = null;
    if (lam && lam.axes && typeof lam.axes === "object") {
      var lkind = kindForLabel(lam.truth_label);
      var ak = Object.keys(lam.axes).slice(0, 8);
      for (i = 0; i < ak.length; i++) {
        var av = Number(lam.axes[ak[i]]);
        var wv = lam.weights && own(lam.weights, ak[i]) ? Number(lam.weights[ak[i]]) : NaN;
        add("lambda axis " + clean(ak[i], 28), place(seedBase, "axis:" + ak[i], (i / Math.max(1, ak.length)) * TAU, 0.24, 0.16),
          lkind, isFinite(av) ? Math.max(0.15, Math.min(1, av)) : 0.15,
          "value " + (isFinite(av) ? av.toFixed(2) : "NONE") + " | weight " + (isFinite(wv) ? wv.toFixed(2) : "NONE") +
          " | label " + clean(lam.truth_label, 16) + " | advisory only, Conjecture 1 open", "lambda");
      }
      lc = lambdaCheck(lam.axes, lam.weights, lam.score);
    }

    chips.push(["VERTICAL " + vname + " | " + product, "ok"]);
    chips.push(["REVISION " + (rev ? rev.slice(0, 12) : "UNKNOWN (server reported no usable revision; layout unseeded)"), rev ? "ok" : "off"]);
    if (ready) {
      chips.push(["READINESS " + clean(ready.status, 24) + " | label " + clean(ready.truth_label, 16), ready.ready === true ? "ok" : "off"]);
      if (live) {
        chips.push(["LIVE READINGS IN SCOPE: " + clean(live.observations, 8) + " observations, " + clean(live.connectors_observed, 8) + " of " + connectors.length + " connectors" +
                    (live.observed_in_scope === true ? "" : " (none fetched this session)"), live.observed_in_scope === true ? "ok" : "note"]);
      }
      if (ready.store && typeof ready.store === "object" && ready.store.durability) {
        chips.push(["STORE " + clean(ready.store.durability, 24), ready.store.durability === "EPHEMERAL_FILE" ? "note" : "ok"]);
      }
    } else {
      chips.push(["READINESS ABSENT from payload", "off"]);
    }
    if (lc) {
      chips.push(["LAMBDA ADVISORY server " + lc.server.toFixed(4) + " | browser recompute " + lc.local.toFixed(4) +
                  (lc.agrees ? " AGREES" : " MISMATCH") + " | reference 0.80 " + (lc.server >= 0.80 ? "met" : "not met") +
                  " | MODELED, not an admission", lc.agrees ? "note" : "off"]);
    }
    chips.push(["GAPS " + gaps + " connector, " + (frayFrom >= 0 ? "cord frays at organ " + (frayFrom + 1) : "cord intact (no unmet requirement reported)"), gaps || frayFrom >= 0 ? "note" : "ok"]);
    chips.push(["MATERIAL KEY: SOLID = reported label MEASURED or tested code; WIREFRAME = MODELED; OUTLINE = advisory or unlabelled; DASHED RING WITH X = gap (absent); POINTS = SAMPLE; RING WITH DOT = REPORTED", "note"]);
    chips.push(["DIGEST-SEEDED LAYOUT: positions come from the build revision hash", "note"]);
    chips.push(["ILLUSTRATIVE LAYOUT - not a measured topology; receipts: none minted, cord shows contract order only", "note"]);

    for (i = 0; i < nodes.length; i++) {
      readout.push(nodes[i].group + " | " + nodes[i].label + " | " + (KIND_NAME[nodes[i].kind] || "LINE") + " | " + nodes[i].text);
    }
    return { nodes: nodes, lines: lines, chips: chips, readout: readout, gaps: gaps,
             frayFrom: frayFrom, lambda: lc, revision: rev, vertical: vname };
  }

  function sceneFromLabels(labels) {
    var nodes = [], lines = [], n = labels.length;
    for (var i = 0; i < n; i++) {
      nodes.push({ label: clean(labels[i], 60), pos: fib(i, n, 1.0), kind: K.SOLID, val: 1, seed: (i % 97) / 97,
                   text: "catalog label", group: "engine" });
    }
    for (var k = 0; k < n - 1; k++) {
      lines.push({ a: nodes[k].pos, b: nodes[k + 1].pos, kind: K.LINE, seed: nodes[k].seed });
    }
    return { nodes: nodes, lines: lines };
  }

  function fib(i, n, r) {
    var phi = Math.acos(1 - 2 * (i + 0.5) / n);
    var th = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
    return [r * Math.sin(phi) * Math.cos(th), r * Math.cos(phi) * 0.72, r * Math.sin(phi) * Math.sin(th)];
  }
  /* V2-MODEL-END */

  var VSH =
    "precision mediump float;" +
    "attribute vec3 aPos;" +
    "attribute vec4 aMeta;" +
    "uniform float uTime;" +
    "uniform float uRotX;" +
    "uniform float uRotY;" +
    "uniform float uZoom;" +
    "uniform float uDpr;" +
    "uniform vec2 uAsp;" +
    "varying float vSeed;" +
    "varying float vKind;" +
    "varying float vVal;" +
    "varying float vDepth;" +
    "void main() {" +
    "  vSeed = aMeta.x; vKind = aMeta.y; vVal = aMeta.z;" +
    "  float cx = cos(uRotX); float sx = sin(uRotX);" +
    "  float cy = cos(uRotY); float sy = sin(uRotY);" +
    "  vec3 p = aPos;" +
    "  p = vec3(p.x, p.y * cx - p.z * sx, p.y * sx + p.z * cx);" +
    "  p = vec3(p.x * cy + p.z * sy, p.y, -p.x * sy + p.z * cy);" +
    "  vDepth = 0.68 + 0.32 * clamp((p.z + 1.6) / 3.2, 0.0, 1.0);" +
    "  gl_Position = vec4(p.x / uZoom * uAsp.x, p.y / uZoom * uAsp.y, 0.0, 1.0);" +
    "  float pulse = 0.85 + 0.15 * sin(uTime * 2.0 + aMeta.x * 6.2831);" +
    "  float sz = 3.0;" +
    "  if (aMeta.y > 5.5 && aMeta.y < 6.5) { sz = 6.4; }" +
    "  else if (aMeta.y > 0.5 && aMeta.y < 5.5) { sz = 5.2; }" +
    "  else if (aMeta.y < 0.5) { sz = 4.0; }" +
    "  gl_PointSize = sz * pulse * (0.45 + 0.55 * aMeta.z) * (5.6 / uZoom) * uDpr;" +
    "}";
  var FSH =
    "precision mediump float;" +
    "uniform float uTime;" +
    "uniform float uGlow;" +
    "uniform float uFlat;" +
    "varying float vSeed;" +
    "varying float vKind;" +
    "varying float vVal;" +
    "varying float vDepth;" +
    "float ringA(float d, float r, float w) { return smoothstep(w, 0.0, abs(d - r)); }" +
    "void main() {" +
    "  float k = vKind;" +
    "  if (k > 9.5) {" +
    "    vec3 lc = vec3(0.35, 0.82, 1.0); float la = 0.26;" +
    "    if (k > 11.5) { lc = vec3(1.0, 0.42, 0.34); la = 0.28 + 0.4 * step(0.5, fract(vSeed * 29.0 + uTime * 0.7)); }" +
    "    else if (k > 10.5) { lc = vec3(0.98, 0.82, 0.45); la = 0.8; }" +
    "    gl_FragColor = vec4(lc, la * vDepth);" +
    "    return;" +
    "  }" +
    "  vec2 c = gl_PointCoord - 0.5;" +
    "  float d = length(c) * 2.0;" +
    "  if (d > 1.0) { discard; }" +
    "  float a = 0.0; vec3 col = vec3(0.35, 0.82, 1.0);" +
    "  if (k < 0.5) {" +
    "    a = smoothstep(1.0, 0.55, d) * 0.9 + 0.35 * uGlow * smoothstep(1.0, 0.0, d);" +
    "    col = mix(vec3(0.35, 0.82, 1.0), vec3(0.98, 0.82, 0.45), vSeed);" +
    "  } else if (k < 1.5) {" +
    "    float cr = (abs(c.x) < 0.035 || abs(c.y) < 0.035) && d < 0.8 ? 0.85 : 0.0;" +
    "    a = max(ringA(d, 0.82, 0.12), cr); col = vec3(0.74, 0.56, 1.0);" +
    "  } else if (k < 2.5) {" +
    "    vec2 g = fract(gl_PointCoord * 3.0) - 0.5;" +
    "    a = smoothstep(0.30, 0.18, length(g)); col = vec3(0.98, 0.82, 0.45);" +
    "  } else if (k < 3.5) {" +
    "    a = ringA(d, 0.84, 0.09); col = vec3(0.80, 0.88, 1.0);" +
    "  } else if (k < 4.5) {" +
    "    float ang = atan(c.y, c.x);" +
    "    float dash = step(0.5, fract(ang * 1.2732 + 0.5));" +
    "    float x = step(abs(abs(c.x) - abs(c.y)), 0.045) * step(d, 0.5);" +
    "    a = max(ringA(d, 0.84, 0.08) * dash, x * 0.9); col = vec3(1.0, 0.68, 0.40);" +
    "  } else if (k < 5.5) {" +
    "    a = max(ringA(d, 0.84, 0.09), smoothstep(0.30, 0.2, d)); col = vec3(0.62, 0.94, 0.75);" +
    "  } else {" +
    "    a = smoothstep(1.0, 0.3, d); col = vec3(0.98, 0.82, 0.45);" +
    "  }" +
    "  float scan = 0.88 + 0.12 * sin(vSeed * 40.0 - uTime * 5.0) * (1.0 - uFlat);" +
    "  float alpha = a * scan * vDepth;" +
    "  if (alpha < 0.02) { discard; }" +
    "  gl_FragColor = vec4(col, alpha);" +
    "}";

  /* ENGINE-BEGIN pinned shared three.js r170 WebGPU engine (same bytes as a11oy). */
  var ENGINE = { url: "/assets/holo/three.webgpu.min.js", bytes: 822115,
                 sha: "9d01bb1bae1badb5071d341f76c3569f6118bad126effd425a06611a9d993035" };
  var eng = null;
  var SPEC = [["sph", 0x59d1ff, 0, 0.032], ["ico", 0xbd8fff, 1, 0.05], ["dot", 0xfad173, 0, 0.011],
              ["tor", 0xcce0ff, 0, 0.05], ["gap", 0xffad66, 0, 0.05], ["tor", 0x9ef0c0, 0, 0.05],
              ["sph", 0xfad173, 0, 0.07]];
  var LINE_RGB = { 4: [0xffad66, 0.95], 10: [0x59d1ff, 0.26], 11: [0xfad173, 0.8], 12: [0xff6b57, 0.6] };

  function hex(buf) {
    return Array.prototype.map.call(new Uint8Array(buf), function (b) { return (b < 16 ? "0" : "") + b.toString(16); }).join("");
  }

  function loadEngine() {
    if (!window.crypto || !window.crypto.subtle) { return Promise.reject(new Error("integrity")); }
    return fetch(ENGINE.url, { credentials: "omit", cache: "force-cache" }).then(function (res) {
      if (!res.ok) { throw new Error("engine"); }
      return res.arrayBuffer();
    }).then(function (buf) {
      if (buf.byteLength !== ENGINE.bytes) { throw new Error("integrity"); }
      return window.crypto.subtle.digest("SHA-256", buf).then(function (d) {
        if (hex(d) !== ENGINE.sha) { throw new Error("integrity"); }
        return import(URL.createObjectURL(new Blob([buf], { type: "text/javascript" })));
      });
    });
  }

  function initThree(T) {
    var base = $(CANVAS_ID), c3 = document.createElement("canvas");
    c3.id = "holo-canvas3d";
    c3.setAttribute("aria-hidden", "true");
    base.parentNode.insertBefore(c3, base);
    var r = new T.WebGPURenderer({ canvas: c3, antialias: true, alpha: true });
    return r.init().then(function () {
      r.setClearColor(0x000000, 0);
      var scene = new T.Scene(), cam = new T.OrthographicCamera(-1, 1, 1, -1, -20, 20), grp = new T.Group();
      cam.position.z = 10;
      scene.add(grp);
      eng = { T: T, r: r, scene: scene, cam: cam, grp: grp, live: [], glowMats: [], fray: null,
              backend: r.backend && r.backend.isWebGPUBackend ? "WebGPU" : "WebGL2" };
    }, function (e) {
      if (c3.parentNode) { c3.parentNode.removeChild(c3); }
      throw e;
    });
  }

  function engineLabel() {
    if (st.mode === "three") { return "ENGINE three.js r170 " + eng.backend + " | same-origin | sha256 verified in this browser"; }
    return "ENGINE raw WebGL fallback" + (st.why ? " | " + st.why : "");
  }

  function ensureRenderer() {
    if (st.rp) { return st.rp; }
    var timer = new Promise(function (_, no) { setTimeout(function () { no(new Error("timeout")); }, 12000); });
    st.rp = Promise.race([loadEngine().then(initThree), timer]).then(function () {
      st.mode = "three";
    }, function (e) {
      var m = e && e.message ? String(e.message) : "";
      st.why = m === "integrity" ? "engine integrity check failed or unavailable" : (m === "engine" || m === "timeout" ? "engine file unavailable" : "engine could not start");
      try { initGL(); st.mode = "raw"; } catch (err) { st.mode = "none"; }
    });
    return st.rp;
  }

  function clearThree() {
    if (!eng) { return; }
    for (var i = 0; i < eng.live.length; i++) {
      var o = eng.live[i];
      eng.grp.remove(o);
      if (o.geometry) { o.geometry.dispose(); }
      if (o.material) { o.material.dispose(); }
    }
    eng.live = []; eng.glowMats = []; eng.fray = null;
  }

  function uploadThree(scene) {
    var T = eng.T, geos = { sph: new T.SphereGeometry(1, 14, 10), ico: new T.IcosahedronGeometry(1, 1),
                            dot: new T.SphereGeometry(1, 6, 4), tor: new T.TorusGeometry(1, 0.1, 6, 28) };
    var groups = {}, gaps = [], i, j;
    clearThree();
    st.nodes = scene.nodes; st.proj = [];
    function put(kind, pos, s) {
      var sp = SPEC[kind], key = kind + sp[0];
      (groups[key] = groups[key] || { sp: sp, kind: kind, items: [] }).items.push([pos, s]);
    }
    for (i = 0; i < scene.nodes.length; i++) {
      var nd = scene.nodes[i], r = SPEC[nd.kind][3] * (0.45 + 0.55 * nd.val) * 1.4;
      st.proj.push([0, 0]);
      if (nd.kind === K.GAP) {
        for (j = 0; j < 12; j += 2) {
          var g0 = j * 0.5236, g1 = (j + 1) * 0.5236;
          gaps.push(nd.pos[0] + Math.cos(g0) * r, nd.pos[1] + Math.sin(g0) * r, nd.pos[2],
                    nd.pos[0] + Math.cos(g1) * r, nd.pos[1] + Math.sin(g1) * r, nd.pos[2]);
        }
        gaps.push(nd.pos[0] - r * 0.5, nd.pos[1] - r * 0.5, nd.pos[2], nd.pos[0] + r * 0.5, nd.pos[1] + r * 0.5, nd.pos[2],
                  nd.pos[0] - r * 0.5, nd.pos[1] + r * 0.5, nd.pos[2], nd.pos[0] + r * 0.5, nd.pos[1] - r * 0.5, nd.pos[2]);
      } else if (nd.kind === K.POINTS) {
        for (j = 0; j < 5; j++) {
          var a = j * 1.2566 + nd.seed * 6.28;
          put(nd.kind, [nd.pos[0] + Math.cos(a) * 0.035, nd.pos[1] + Math.sin(a) * 0.035, nd.pos[2]], r);
        }
      } else {
        put(nd.kind, nd.pos, r);
      }
      if (nd.kind === K.REPORTED) { groups["5dot"] = groups["5dot"] || { sp: ["dot", 0x9ef0c0, 0], kind: 5, items: [] }; groups["5dot"].items.push([nd.pos, r * 0.4]); }
    }
    Object.keys(groups).forEach(function (key) {
      var g = groups[key], m = new T.Matrix4(), mat = new T.MeshBasicMaterial({
        color: g.sp[1], wireframe: !!g.sp[2], transparent: true, opacity: 0.9,
        blending: T.AdditiveBlending, depthWrite: false });
      var mesh = new T.InstancedMesh(geos[g.sp[0]], mat, g.items.length);
      for (var n = 0; n < g.items.length; n++) {
        var it = g.items[n];
        m.compose(new T.Vector3(it[0][0], it[0][1], it[0][2]), new T.Quaternion(), new T.Vector3(it[1], it[1], it[1]));
        mesh.setMatrixAt(n, m);
      }
      eng.grp.add(mesh); eng.live.push(mesh);
      if (g.kind === K.SOLID || g.kind === K.CORE) { eng.glowMats.push(mat); }
    });
    [4, 10, 11, 12].forEach(function (lk) {
      var pts = lk === 4 ? gaps : [];
      for (var q = 0; q < scene.lines.length && lk !== 4; q++) {
        var l = scene.lines[q];
        if (l.kind === lk) { pts.push(l.a[0], l.a[1], l.a[2], l.b[0], l.b[1], l.b[2]); }
      }
      if (!pts.length) { return; }
      var geo = new T.BufferGeometry();
      geo.setAttribute("position", new T.Float32BufferAttribute(pts, 3));
      var mat = new T.LineBasicMaterial({ color: LINE_RGB[lk][0], transparent: true, opacity: LINE_RGB[lk][1], depthWrite: false });
      var seg = new T.LineSegments(geo, mat);
      eng.grp.add(seg); eng.live.push(seg);
      if (lk === 12) { eng.fray = mat; }
    });
    Object.keys(geos).forEach(function (k) { geos[k].dispose(); });
    st.ready = true;
  }

  function renderThree(t) {
    var stage = document.querySelector(".holo-stage");
    if (!stage) { return; }
    var w = Math.max(1, stage.clientWidth), h = Math.max(1, stage.clientHeight);
    var ax = w > h ? h / w : 1, ay = w > h ? 1 : w / h;
    eng.cam.left = -st.zoom / ax; eng.cam.right = st.zoom / ax;
    eng.cam.top = st.zoom / ay; eng.cam.bottom = -st.zoom / ay;
    eng.cam.updateProjectionMatrix();
    eng.grp.rotation.set(st.rotX, st.rotY, 0, "YXZ");
    st.glow = st.view === "engines" ? 1 : ageGlow();
    for (var i = 0; i < eng.glowMats.length; i++) { eng.glowMats[i].opacity = 0.9 * st.glow; }
    if (eng.fray) { eng.fray.opacity = REDUCED ? 0.6 : 0.35 + 0.35 * Math.abs(Math.sin(t * 3)); }
    eng.r.render(eng.scene, eng.cam);
    updateProjection();
  }
  /* ENGINE-END */

  function compile(gl, kind, src) {
    var sh = gl.createShader(kind);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) { throw new Error("shader"); }
    return sh;
  }

  function initGL() {
    if (st.gl) { return; }
    var canvas = $(CANVAS_ID);
    if (!canvas) { throw new Error("canvas missing"); }
    var gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    if (!gl) { throw new Error("webgl unavailable"); }
    var prog = gl.createProgram();
    gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VSH));
    gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FSH));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { throw new Error("link"); }
    gl.useProgram(prog);
    st.gl = gl; st.prog = prog;
    st.loc = {};
    ["uTime", "uRotX", "uRotY", "uZoom", "uDpr", "uAsp", "uGlow", "uFlat"].forEach(function (n) {
      st.loc[n] = gl.getUniformLocation(prog, n);
    });
    st.loc.aPos = gl.getAttribLocation(prog, "aPos");
    st.loc.aMeta = gl.getAttribLocation(prog, "aMeta");
    st.posBuf = gl.createBuffer();
    st.lineBuf = gl.createBuffer();
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.clearColor(0, 0, 0, 0);
  }

  function uploadScene(scene) {
    if (st.mode === "three") { uploadThree(scene); return; }
    initGL();
    var gl = st.gl;
    var nodes = scene.nodes, n = nodes.length, i;
    var pos = new Float32Array(n * 7);
    st.nodes = nodes;
    st.proj = [];
    for (i = 0; i < n; i++) {
      var p = nodes[i].pos, o = i * 7;
      pos[o] = p[0]; pos[o + 1] = p[1]; pos[o + 2] = p[2];
      pos[o + 3] = nodes[i].seed; pos[o + 4] = nodes[i].kind; pos[o + 5] = nodes[i].val; pos[o + 6] = 0;
      st.proj.push([0, 0]);
    }
    var lp = [];
    for (i = 0; i < scene.lines.length; i++) {
      var l = scene.lines[i];
      lp.push(l.a[0], l.a[1], l.a[2], l.seed, l.kind, 1, 0,
              l.b[0], l.b[1], l.b[2], l.seed, l.kind, 1, 0);
    }
    st.lineCount = scene.lines.length * 2;
    gl.bindBuffer(gl.ARRAY_BUFFER, st.posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, st.lineBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(lp), gl.STATIC_DRAW);
    st.ready = true;
  }

  function sizeRenderer() {
    var stage = document.querySelector(".holo-stage"), canvas = $(CANVAS_ID);
    if (!stage || !canvas || !(st.gl || st.mode === "three")) { return; }
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.max(1, stage.clientWidth), h = Math.max(1, stage.clientHeight);
    if (st.mode === "three") { eng.r.setPixelRatio(dpr); eng.r.setSize(w, h, false); return; }
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    st.gl.viewport(0, 0, canvas.width, canvas.height);
    st.gl.uniform1f(st.loc.uDpr, dpr);
    st.gl.uniform2f(st.loc.uAsp, w > h ? h / w : 1, w > h ? 1 : w / h);
  }

  function bindBuf(buf) {
    var gl = st.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.enableVertexAttribArray(st.loc.aPos);
    gl.vertexAttribPointer(st.loc.aPos, 3, gl.FLOAT, false, 28, 0);
    gl.enableVertexAttribArray(st.loc.aMeta);
    gl.vertexAttribPointer(st.loc.aMeta, 4, gl.FLOAT, false, 28, 12);
  }

  function ageGlow() {
    if (!st.fetchedAt) { return 1; }
    var age = Math.max(0, (Date.now() - st.fetchedAt) / 1000);
    return Math.max(0.2, 1 - 0.8 * Math.min(1, age / AGE_FULL_S));
  }

  function render(t) {
    if (st.mode === "three") {
      if (!st.ready) { return; }
      try { renderThree(t); } catch (err) { failClosed("RENDER FAILED - failing closed"); }
      return;
    }
    if (!st.gl || !st.ready) { return; }
    var gl = st.gl;
    gl.useProgram(st.prog);
    gl.uniform1f(st.loc.uTime, t);
    gl.uniform1f(st.loc.uRotX, st.rotX);
    gl.uniform1f(st.loc.uRotY, st.rotY);
    gl.uniform1f(st.loc.uZoom, st.zoom);
    gl.uniform1f(st.loc.uFlat, REDUCED ? 1 : 0);
    st.glow = st.view === "engines" ? 1 : ageGlow();
    gl.uniform1f(st.loc.uGlow, st.glow);
    gl.clear(gl.COLOR_BUFFER_BIT);
    if (st.lineCount) {
      bindBuf(st.lineBuf);
      gl.drawArrays(gl.LINES, 0, st.lineCount);
    }
    bindBuf(st.posBuf);
    gl.drawArrays(gl.POINTS, 0, st.nodes.length);
    updateProjection();
  }

  function updateProjection() {
    var stage = document.querySelector(".holo-stage");
    if (!stage) { return; }
    var w = stage.clientWidth, h = stage.clientHeight;
    var ax = w > h ? h / w : 1, ay = w > h ? 1 : w / h;
    var cx = Math.cos(st.rotX), sx = Math.sin(st.rotX);
    var cy = Math.cos(st.rotY), sy = Math.sin(st.rotY);
    for (var i = 0; i < st.nodes.length; i++) {
      var p = st.nodes[i].pos;
      var y1 = p[1] * cx - p[2] * sx;
      var z1 = p[1] * sx + p[2] * cx;
      var x2 = p[0] * cy + z1 * sy;
      st.proj[i] = [((x2 / st.zoom * ax) * 0.5 + 0.5) * w,
                    ((-y1 / st.zoom * ay) * 0.5 + 0.5) * h];
    }
  }

  function frame(now) {
    if (!st.open || !(st.gl || st.mode === "three")) { return; }
    var t = now / 1000;
    if (!REDUCED && !st.drag) { st.rotY += 0.0022; }
    render(t);
    if (now - st.tick > 1000) { st.tick = now; ageChip(); }
    if (!REDUCED) { st.raf = requestAnimationFrame(frame); }
  }

  var ageEl = null;
  function ageChip() {
    if (!ageEl || st.view === "engines" || !st.fetchedAt) { return; }
    var age = Math.round((Date.now() - st.fetchedAt) / 1000);
    ageEl.textContent = "READING AGE " + age + "s since this page fetched it (glow fades over " + (AGE_FULL_S / 60) + " min)";
  }

  function setReadout(lines) {
    var ul = $(READOUT_ID);
    if (!ul) { return; }
    while (ul.firstChild) { ul.removeChild(ul.firstChild); }
    for (var i = 0; i < lines.length; i++) {
      var li = document.createElement("li");
      li.textContent = lines[i];
      ul.appendChild(li);
    }
  }

  function setOffline(msg) {
    var off = $(OFFLINE_ID);
    if (off) { off.textContent = msg; off.hidden = !msg; }
  }

  function activate(view) {
    st.view = view;
    st.zoom = view === "engines" ? 2.1 : 1.55;
    var btns = document.querySelectorAll("#" + VIEWS_ID + " button");
    for (var i = 0; i < btns.length; i++) {
      btns[i].setAttribute("aria-pressed", btns[i].getAttribute("data-view") === view ? "true" : "false");
    }
    var title = $(TITLE_ID);
    if (title) { title.textContent = view === "engines" ? "Engine constellation" : "Vertical frontier: " + view; }
  }

  function failClosed(msg) {
    st.ready = false; st.nodes = []; st.proj = []; st.lineCount = 0;
    if (st.mode === "three") { clearThree(); try { eng.r.render(eng.scene, eng.cam); } catch (err) { /* nothing left to draw */ } }
    else if (st.gl) { st.gl.clear(st.gl.COLOR_BUFFER_BIT); }
    setReadout([]);
    clearHud();
    setOffline(msg);
    chip(msg, "off");
  }

  function show(view) {
    var seq = ++st.seq;
    activate(view);
    setOffline("");
    clearHud();
    ageEl = null;
    var isEngines = view === "engines";
    var p = isEngines ? fetchFeed() : fetchFrontier(view);
    return p.then(function (payload) {
      if (seq !== st.seq) { return; }
      var scene, extra = null;
      if (isEngines) {
        var labels = collectNodes(payload);
        if (!labels.length) { throw new Error("rejected: no catalog nodes"); }
        scene = sceneFromLabels(labels);
        st.fetchedAt = 0;
        uploadScene(scene);
        sizeRenderer();
        setReadout(labels);
        chip("catalog nodes " + labels.length, "ok");
        chip("ILLUSTRATIVE LAYOUT - procedural, not measured", "note");
        chip(engineLabel(), st.mode === "three" ? "ok" : "note");
      } else {
        st.fetchedAt = Date.now();
        extra = buildVerticalScene(payload, view, st.fetchedAt);
        if (!extra || !extra.nodes.length) { throw new Error("rejected: frontier payload"); }
        uploadScene(extra);
        sizeRenderer();
        setReadout(extra.readout);
        for (var i = 0; i < extra.chips.length; i++) { chip(extra.chips[i][0], extra.chips[i][1]); }
        chip(engineLabel(), st.mode === "three" ? "ok" : "note");
        ageEl = chip("READING AGE 0s since this page fetched it", "note");
      }
      render(0);
      if (st.open && !REDUCED && !st.raf) { st.raf = requestAnimationFrame(frame); }
    }, function () {
      if (seq !== st.seq) { return; }
      failClosed(isEngines ? "CATALOG UNREACHABLE - failing closed" : "FRONTIER UNREACHABLE - failing closed");
    }).catch(function (err) {
      if (seq !== st.seq) { return; }
      var m = err && err.message ? String(err.message) : "";
      if (m.indexOf("rejected") === 0) {
        failClosed(isEngines ? "CATALOG EMPTY - failing closed" : "FRONTIER PAYLOAD REJECTED (schema or vertical mismatch) - failing closed");
      } else if (m === "webgl unavailable" || m === "shader" || m === "link" || m === "canvas missing") {
        failClosed("WEBGL UNAVAILABLE - failing closed");
      } else {
        failClosed("RENDER FAILED - failing closed");
      }
    });
  }

  function openPanel() {
    var panel = $(PANEL_ID);
    if (!panel) { return; }
    st.open = true;
    st.lastFocus = document.activeElement;
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    if (!st.ready) {
      ensureRenderer().then(function () {
        if (st.mode === "none") { failClosed("WEBGL UNAVAILABLE - failing closed"); return; }
        sizeRenderer();
        show(st.view);
      });
    } else {
      sizeRenderer(); render(0);
      if (!REDUCED && !st.raf) { st.raf = requestAnimationFrame(frame); }
    }
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
    var views = $(VIEWS_ID);
    if (views) {
      views.addEventListener("click", function (e) {
        var b = e.target && e.target.closest ? e.target.closest("button[data-view]") : null;
        if (!b) { return; }
        var v = b.getAttribute("data-view");
        if (v === "engines" || VERTICALS.indexOf(v) >= 0) { show(v); }
      });
    }
    panel.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { closePanel(); return; }
      if (e.key === "Tab") {
        var focusables = [$("holo-close")].concat(Array.prototype.slice.call(document.querySelectorAll("#" + VIEWS_ID + " button")), [$(CANVAS_ID), document.querySelector("#holo-details summary")]).filter(Boolean);
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
        var nd = st.nodes[best];
        tip.textContent = nd.label + " | " + (KIND_NAME[nd.kind] || "") + (nd.text && nd.text !== "catalog label" ? " | " + nd.text : "");
        tip.style.left = st.proj[best][0] + "px";
        tip.style.top = st.proj[best][1] + "px";
        tip.style.opacity = 1;
      } else { tip.style.opacity = 0; }
    });
    canvas.addEventListener("wheel", function (e) {
      e.preventDefault();
      st.zoom = Math.max(0.9, Math.min(6, st.zoom + e.deltaY * 0.0016));
      if (REDUCED) { render(0); }
    }, { passive: false });
    var stage = document.querySelector(".holo-stage");
    if (typeof ResizeObserver === "function" && stage) {
      st.ro = new ResizeObserver(function () { if (st.open) { sizeRenderer(); if (REDUCED) { render(0); } } });
      st.ro.observe(stage);
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
<section id="holo-panel" role="dialog" aria-modal="true" aria-label="3D holographic engine constellation and vertical frontier" aria-hidden="true">
<header><h2 id="holo-title">Engine constellation</h2><button id="holo-close" type="button">Close (Esc)</button></header>
<div id="holo-views" role="group" aria-label="Choose a view">
<button type="button" data-view="engines" aria-pressed="true">Engines</button>
<button type="button" data-view="finance" aria-pressed="false">Finance</button>
<button type="button" data-view="terra" aria-pressed="false">Terra</button>
<button type="button" data-view="counsel" aria-pressed="false">Counsel</button>
<button type="button" data-view="lyte" aria-pressed="false">Lyte</button>
<button type="button" data-view="killinchu" aria-pressed="false">Killinchu</button>
<button type="button" data-view="sentra" aria-pressed="false">Sentra</button>
</div>
<div class="holo-stage">
<canvas id="holo-canvas" tabindex="0" aria-label="Interactive 3D holographic view of the governed engine catalog or one vertical frontier; the text readout below lists every item"></canvas>
<p id="holo-offline" hidden>CATALOG UNREACHABLE - failing closed</p>
<div id="holo-hud" role="status" aria-live="polite"></div>
<div id="holo-tip" aria-hidden="true"></div>
</div>
<details id="holo-details"><summary>Text readout (every node, material and label)</summary><ul id="holo-readout"></ul></details>
<p class="holo-note">ILLUSTRATIVE LAYOUT - node positions are procedural or digest-seeded, never a measured topology. Material shows the label the server reports: solid, wireframe, points, outline or gap; the exact label is always written out. No candidate text crosses this surface.</p>
</section>
"""
