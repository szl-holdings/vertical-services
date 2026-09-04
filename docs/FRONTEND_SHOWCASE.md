# Executable Vertical Front-End Concepts

`frontier_fabric.showcase` renders ten dependency-free, mobile-responsive,
keyboard-accessible concept surfaces from the same governed product contract as
the Python backend.

These are implementation starters and review artifacts. They are not a claim
that the canonical product domains have already adopted or deployed each
concept.

## Run with FastAPI

```python
from fastapi import FastAPI
from frontier_fabric.fastapi_router import create_router
from frontier_fabric.showcase import create_showcase_router

app = FastAPI()
app.include_router(create_router())
app.include_router(create_showcase_router())
```

Routes:

```text
GET /vertical-frontier/
GET /vertical-frontier/a11oy
GET /vertical-frontier/hatun
GET /vertical-frontier/killinchu
GET /vertical-frontier/sentra
GET /vertical-frontier/lyte
GET /vertical-frontier/puriq-finance
GET /vertical-frontier/terra
GET /vertical-frontier/prism-counsel
GET /vertical-frontier/living-anatomy
GET /vertical-frontier/szl-atlas
```

## Render without a framework

```python
from pathlib import Path
from frontier_fabric.showcase import render_showcase_index, render_vertical_showcase

output = Path("/tmp/szl-frontier")
output.mkdir(parents=True, exist_ok=True)
(output / "index.html").write_text(render_showcase_index(), encoding="utf-8")
for vertical_id in (
    "a11oy",
    "hatun",
    "killinchu",
    "sentra",
    "lyte",
    "puriq-finance",
    "terra",
    "prism-counsel",
    "living-anatomy",
    "szl-atlas",
):
    page = output / vertical_id / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(render_vertical_showcase(vertical_id), encoding="utf-8")
```

## Original interaction systems

- **A11oy:** decision trajectory and policy chamber.
- **Hatun:** temporal council and confidence-drift constellation.
- **Killinchu:** synthetic radar, rules-boundary ring, and mission simulation.
- **Sentra:** exposure nervous system and remediation proof stack.
- **Lyte:** causal trace river from deployment to measured business impact.
- **PURIQ Finance:** filing mosaic, scenario fan, and invalidation condition.
- **Terra:** parcel strata, ownership history, and zoning delta.
- **PRISM Counsel:** issue prism, argument lattice, authority rail, and review
  stamp.
- **Living Anatomy:** bioluminescent organ body with bounded injury simulation.
- **SZL Atlas:** artifact constellation and source-binding beacon.

Every surface includes the vertical's operator outcome, unmet need, evidence
contract, effect mode, and public-actuation state. The concepts use no external
scripts, fonts, tracking, or imagery.

## Production adoption gate

A canonical product may consume the concept only after its own PR proves:

- route and information architecture match that product's lane;
- data comes from a declared connector or operator-owned source;
- model and kernel identities are exact and runtime-bound;
- all unavailable, partial, stale, denied, and tampered states are represented;
- responsive and accessibility checks pass at the required viewports;
- no competitor trade dress or proprietary material was copied;
- deployment and live readback are bound to an exact source revision.
