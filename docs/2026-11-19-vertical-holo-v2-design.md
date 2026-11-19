# Vertical holo v2: design and code verification (2026-11-19)

Owner directive (2026-11-15, unchanged): all spaces fully 3D holographic.
Scope: the six vertical-services Spaces (finance/PURIQ, terra, counsel, lyte,
killinchu/vessels, sentra). Surface: the front-door panel in
deploy/szl_verticals/holo3d.py. Doctrine: docs/HOLO3D_FRONT_DOOR.md.

## Decision

Option B was chosen: one engine, six verticals, each rendering its own real
server data. This PR delivers the data binding and the honesty semantics on the
existing self-contained WebGL panel. It deliberately does not vendor the 822,115
byte three.webgpu.min.js build (r170, MIT, pinned by sha256 in a11oy) into this
Space yet, because:

1. The v1 contract (tests/test_holo3d_contract.py) requires a self-contained,
   bounded script (JS under 45,000 characters, no http:// or https:// strings,
   no external assets). An 822 KB inline engine breaks that bound, and a
   separate static asset route is a new publishing surface that needs its own
   review.
2. A WebGPU path cannot be verified without a GPU browser, and the box can only
   exercise software WebGL.

The scene model is pure data (buildVerticalScene) with no renderer
dependency, so a shared three.js engine can replace the WebGL draw calls later
without changing the honesty rules or the tests. Follow-up, needs a decision:
vendor the engine with the sha256 pin and relax the size bound in one reviewed
change.

## What is drawn, and from which field

| Element | Source field in /api/verticals/{v}/frontier | Material |
|---|---|---|
| Core | product, domain | solid, large |
| 9 organs on a khipu cord | anatomy.organs, anatomy.truth_label | by label: MEASURED solid |
| Cord fray | readiness.requirements (false value) mapped to the organ it gates | red dashed cord from that organ |
| Formulas | formulas[].status verbatim | solid / wireframe / outline per table |
| Connectors | connectors[].state, readiness.live_data | gap, with the reason written out |
| Lambda axes | readiness.lambda_advisory.axes and weights | wireframe (label MODELED), size by value |
| Lambda check | lambda_advisory.score vs browser recompute | chip: AGREES or MISMATCH |

Requirement to organ mapping used for the fray: required_connector_contracts_ready
gates sense, source_bound gates context, formula_registry_bound gates formula,
observation_store_writable gates remember, persistent_signing_key gates receipt.

Label table: MEASURED solid, MODELED wireframe, SAMPLE points, ROADMAP outline,
UNAVAILABLE gap, REPORTED ring with a dot, anything else outline plus a written
UNRECOGNISED note. Status table is in the HOLO3D_FRONT_DOOR.md v2 section. Colour
is never the only signal: every node has a shape, a tooltip and a line in the
text readout.

## Checked against the code (corrections to the first draft)

- The receipt verify route is not mounted in the deployed app (deploy/app.py
  includes no such router), so the cord is not presented as a receipt chain.
  The scene states "receipts: none minted, cord shows contract order only".
- Connector readings carry truth_label REPORTED when state is OBSERVED
  (official_connectors.py) and UNAVAILABLE otherwise. They are never MEASURED.
  The section-level MEASURED on anatomy and readiness describes the contract
  and build, not a data reading.
- Reading a connector is POST /api/verticals/{v}/connectors/{id}/fetch and needs
  the X-SZL-Session header (core.session_scope). GET /frontier needs no session.
  The page therefore never fetches readings and cannot invent them. It cannot
  keep a session id either: sessionStorage and the other persistence APIs are
  forbidden by the v1 contract.
- Live check on 2026-11-19 at revision 7ce6f9e: all six verticals return
  szl.vertical-frontier/v3 (killinchu and the vessels alias both resolve to
  killinchu). counsel really has one connector in state AUTH_REQUIRED
  (congress-bills), which the scene draws as a labelled gap. No vertical has any
  reading in scope, so every connector is a gap with reason no_reading_in_scope.
- The a11oy admit rule is a weighted geometric mean with a 0.80 threshold. The
  vertical Lambda has the same form (Lambda_w(x) = product of x_i^w_i) but is
  advisory and MODELED; Conjecture 1 (uniqueness) is open. The 0.80 marker is
  shown as a reference only.

## Rejected

AI-generated 3D (TRELLIS, Hunyuan3D, DINOv3-based models) for licence reasons.
Geometry is procedural from real data.

## Not done here

- Shared three.js WebGPU engine (above).
- Per-connector readings in the scene (needs a user-initiated session fetch).
- A receipt-verification fray (needs the verify route mounted).
