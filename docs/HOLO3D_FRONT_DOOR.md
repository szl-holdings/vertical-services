# holo3d v1 - front-door 3D engine constellation (2026-11-15)

The vertical-services front door (/) mounts a fully 3D holographic
constellation of the governed engine catalog, rendered client-side with
self-contained WebGL (no external assets or libraries of any kind).

Doctrine:

- Same-origin feed only: the client reads /api/catalog with
  credentials "same-origin" and cache "no-store".
- Fails closed: when the catalog is unreachable the panel shows
  CATALOG UNREACHABLE - failing closed and renders nothing else.
- Honest labelling: node positions are procedural (Fibonacci sphere) and
  labelled ILLUSTRATIVE LAYOUT; they are never a measured topology. Only
  catalog labels are displayed; no candidate text crosses this surface.
- No persistence APIs, no tracking, no external URLs, no eval.
- Accessibility: dialog semantics with focus trap and Escape, reduced-motion
  static rendering, forced-colors support, 44px minimum targets.

Leaders leveraged (2026-11-15 sweep): spatial-hud instanced-particle GLSL,
HOLO.SYS scanline holographic shaders, Brain-Storm measured-vs-rendered
honesty labelling.

Surface: https://szlholdings-vertical-services.hf.space (landing page).
Source: deploy/szl_verticals/holo3d.py (rendered inline by deploy/app.py).
Receipt schema: szl.holo3d/v1. Owner directive (2026-11-15): all spaces fully
3D holographic.

2026-11-15 v1.1: the live /api/catalog returns engines as an object keyed by engine name (sentra, lyte, killinchu, finance, terra, counsel) with aliases arrays, not an array of engine dicts. collectNodes now accepts both shapes (object-keyed and array) so the constellation renders the real catalog; the render helper was simplified with no behavior change.

## v2 (2026-11-19): vertical frontier scene

The same mount gains a second same-origin, read-only feed,
GET /api/verticals/{vertical}/frontier (schema szl.vertical-frontier/v3), and a
view switch for the six verticals (finance, terra, counsel, lyte, killinchu,
sentra). The v1 constellation is still the default view and its doctrine is
unchanged. v2 renders what the server reports and nothing else:

- Anatomy organs are knots on a khipu cord in contract order. The cord frays
  from the first organ whose reported readiness requirement is not true. It is
  not a receipt chain: no receipt is minted by a page view, and the receipt
  verify route is not mounted in the deployed app, so none is claimed.
- Formulas take their material from the server status string (tested or
  deterministic implementation = solid, MODELED = wireframe, ADVISORY and
  policy parameters = outline, unrecognised = outline plus a visible
  UNRECOGNISED STATUS note). The exact status is always written in the tooltip
  and the text readout.
- Connectors are gaps (dashed ring with an X) when the contract state is not
  READY (for example AUTH_REQUIRED) or when no reading exists in scope. A
  reading would arrive through a POST fetch that needs a per-browser
  X-SZL-Session header and is labelled REPORTED, never MEASURED; the scene does
  not fetch readings. A REPORTED label renders as its own ring-with-dot and is
  never promoted.
- The advisory Lambda roll-up is recomputed in the browser as a weighted
  geometric mean and shown beside the server score with AGREES or MISMATCH. The
  0.80 marker is the a11oy reference threshold, shown as a reference only; the
  vertical Lambda is MODELED and advisory, not an admission.
- Layout is seeded from the build revision hash, so it is reproducible and
  moves if the revision changes. It is labelled ILLUSTRATIVE LAYOUT and DIGEST-
  SEEDED, never a measured topology. Glow fades with the age of the page's own
  fetch (client clock, 10 minutes to the floor); no server timestamp is implied.
- Fails closed: wrong schema, wrong vertical or an unreachable feed renders
  nothing but FRONTIER UNREACHABLE - failing closed.
- Also fixed in v2: the v1 shaders declared uTime with different precision in
  the vertex and fragment stages, which strict ANGLE drivers reject at link
  time; both stages now use mediump. Canvas sizing now follows the stage
  instead of a fixed 90px offset.

Receipt schema: szl.holo3d/v2. Contract tests: tests/test_holo3d_contract.py
(unchanged) and tests/test_holo3d_v2_contract.py (runs the client model under
node against the real in-process /frontier payloads). Design and verification
notes: docs/2026-11-19-vertical-holo-v2-design.md.
