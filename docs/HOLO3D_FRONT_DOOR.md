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
