# Dated research briefs in the vertical second brain

The operational fabric accepts bounded research briefs for each existing canonical
vertical. A brief preserves source publication dates, event dates, review timestamps,
optional data periods, source facts, product inferences, and ranked opportunities
with dependencies and acceptance criteria.

## API

- `POST /api/verticals/{vertical}/briefs` validates and stores one brief.
- `GET /api/verticals/{vertical}/briefs?limit=10` returns that session's briefs.
- `GET /api/verticals/{vertical}/second-brain` includes recent brief summaries.

All endpoints use the existing `X-SZL-Session` contract. This is a caller-selected
session boundary, not independent proof of identity or an enterprise authentication
system. A deployment requiring authenticated tenancy must enforce it at its existing
gateway. Never publish session tokens in source, receipts, or brief URLs.

Canonical runtime keys are `terra`, `killinchu`, `sentra`, `lyte`, `finance`,
and `counsel`; existing aliases apply. Vessels maps to Killinchu; Aegis/Defend
uses the Sentra engine. David Leads has its own repository/runtime, and Carlota
Jo has no entry in this registry. This change does not silently add those routes.

## Evidence boundary

Research is always `CALLER_REPORTED` and `REVIEW_REQUIRED`. A source's
`verified_at` records the submitter's review claim. The service does not fetch
source URLs or independently verify the article, provider entitlement, factual
claim, or implementation status. Content hashes establish content identity only;
no signature or deployment is claimed.

Briefs occupy a separate SQLite table in the existing state database. They never
enter connector observations, readiness counts, inference evidence floors, or
effectors. A fact supported by a reviewed news page must still pass the relevant
connector's admission path before it can become runtime evidence.

The state database follows `SZL_STATE_PATH` and `SZL_STATE_DURABILITY`.
File-backed storage survives process restarts only while that file is retained;
the default is explicitly ephemeral. Production durability requires a persistent
mount and operator configuration.

## Payload and limits

The versioned example bundle is [`briefings/2026-10-13.json`](briefings/2026-10-13.json).
Each value in its `briefs` mapping is a complete POST body. `week_start` is the
Monday issue date, while the bundle's research window declares the lookback dates.
Source date-only values avoid inventing a publication time. Event dates may differ
from publication dates and may describe a future scheduled event. `verified_at`
must be timezone-aware, not in the future, and on/after the publication date.

`DEVELOPMENTS` requires sources, developments and opportunities. For a quiet week,
use `NO_MATERIAL_CHANGE`, a nonblank `coverage_note`, and empty development and
opportunity lists; reviewed sources remain optional. Unknown source references,
duplicate IDs, invalid date periods, extra fields and oversized requests are rejected.

Each brief permits at most 12 sources, 16 developments and 16 opportunities, with
64,000 stored UTF-8 bytes. Each vertical/session retains at most 104 distinct briefs;
capacity returns an error instead of silently deleting history. An identical
submission returns the original record and timestamp. Changed content is a new
record, not an overwrite or an assertion that the previous record was corrected.

## Import a reviewed bundle

After deploying a revision that contains these routes, use a local session secret
and an explicitly selected service origin. This example uses only the six known
canonical runtime keys, sends no provider secrets, and does not follow redirects.

```python
import json
import os
from pathlib import Path

import httpx

bundle = json.loads(Path('docs/briefings/2026-10-13.json').read_text())
origin = os.environ['SZL_VERTICAL_ORIGIN'].rstrip('/')
session = os.environ['SZL_BRIEF_SESSION']
with httpx.Client(timeout=20, follow_redirects=False) as client:
    for vertical, body in bundle['briefs'].items():
        if vertical not in {'terra', 'killinchu', 'sentra', 'lyte', 'finance', 'counsel'}:
            raise ValueError('unknown canonical vertical')
        result = client.post(
            f'{origin}/api/verticals/{vertical}/briefs',
            headers={'X-SZL-Session': session}, json=body,
        )
        result.raise_for_status()
        record = result.json()
        print(vertical, record['content_sha256'], record['inserted'])
```

This bundle contains research summaries and proposals, not provider integrations.
Commercial feeds still require actual licensing, authorized credentials, compatible
schemas, and adapter tests. Adding the source change or opening its PR does not
establish Hugging Face deployment or propagation to the product/proof domains.

## Verification

`python -m pytest tests/test_vertical_briefs.py -q` covers session separation,
canonical aliases, persistence across store instances, idempotency, bounded input,
date chronology, no-change weeks, API/second-brain integration and rejection by
the existing connector evidence resolver. Run the full `tests` suite before merge.
