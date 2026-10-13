# Native Vertical Services presentation

The Space's existing `deploy/Dockerfile` serves `deploy/app.py`. Its public HTML
owners are `_landing_page`, `szl_verticals.frontier._experience_html`, and
`szl_verticals.showcase._page`. They now use one presentation-only module,
`deploy/szl_verticals/presentation.py`, for the exact native icon, canonical
tokens, and shared interface roles.

This covers `/`, the six `/experience/{vertical}` pages, and the six
`/intelligence/{vertical}` pages. The separate `frontier/` runtime is not the
source of this Space's deployed shell.

## Design and evidence

The root uses the canonical graphite palette and a distinct coral Workspace
action. The six domain rooms retain their existing colors, motifs, copy,
formulas, source observations, connector states, model bindings and operational
limits. Family navigation wraps at narrow widths. Evidence labels have a 12px
minimum, and the native icon replaces the former decorative approximation.

The token payload and original 32px Orbit SVG are exact embedded subsets of
accepted `szl-brand` sources. `NATIVE_PRESENTATION.json` records both immutable
revisions, source paths and SHA-256 hashes. This is **not** a complete KANCHAY
bundle installation. The closed deployment continues copying the existing
`szl_verticals/` package; no additional publisher mapping is needed.

The icon is displayed at its approved 32px size with 8px clear space. Brand
artwork is © 2026 SZL Holdings, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
reproduced without modification. Component code is Apache-2.0.

## Local qualification

Run the existing Python suite with the repository's pinned application and test
requirements. The native projection tests verify the embedded asset bytes and
the existing container copy boundary.

`tools/check_responsive.mjs` continues to exercise the existing route matrix.
It now also checks the exact native icon size and clear space, visible family
navigation, one H1, readable evidence labels, forced colors and no-script access.
Every browser request is limited to GET on the local preview's origin. The
runner never clicks model, connector, or business action controls.

For the existing localhost preview, set `PREVIEW_BASE_URL`,
`EXPECTED_SOURCE_REVISION`, `PLAYWRIGHT_MODULE_PATH` and `RESPONSIVE_ROUTES` as in
`responsive-ui.yml`. `CHROMIUM_EXECUTABLE` optionally selects an installed local
browser; `RESPONSIVE_REPORT_DIR` optionally places retained evidence outside the
checkout. Default CI artifact locations remain unchanged.

The 200% and 400% cases use CSS zoom to test content reflow. The report labels
that scope and records whether the working tree was dirty. These are local
presentation observations, not live publication, provider, model, or readiness
proof. The existing `hf-space.yml` controller and its source admission/readback
remain authoritative for delivery.
