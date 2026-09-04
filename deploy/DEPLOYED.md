# Deployment contract — SZLHOLDINGS/vertical-services

The combined runtime is published only by `.github/workflows/hf-space.yml` from the exact current `main` commit.

Canonical engines in `deploy/app.py`:

| Route | Role |
|---|---|
| `/sentra` | compatibility lobe (Defend/Aegis policy gates) |
| `/lyte` | observability engine |
| `/killinchu` | canonical defense + maritime product |
| `/vessels` | compatibility lobe only (`_szl_killinchu_lobe`) |
| `/finance` | PURIQ finance engine |
| `/terra` | real-estate engine |
| `/counsel` | PRISM counsel engine |

Do not treat this file as a live occupancy receipt. `/api/build-info` is the single runtime record. Brand on the landing page renders `VERSION` from `szl_verticals.core` (currently `2.2.0`).

The governed publisher:

1. runs network-free contract tests;
2. ensures `SENTRA_SIGNING_KEY` exists without rotating an existing value;
3. derives the Space artifact set from `deploy/Dockerfile`;
4. commits that set atomically to `SZLHOLDINGS/vertical-services`;
5. binds `SZL_SOURCE_REVISION` to the exact GitHub SHA;
6. restarts the Space;
7. attests the exact HF commit and all declared smoke routes;
8. retains immutable deployment evidence as a GitHub Actions artifact.

The historical `SZLHOLDINGS/vessels` Space is retained. Vessels is consolidated into Killinchu as the public maritime surface, while the executable risk engine remains available at `/vessels` in this combined service.

The Space tree copies only `deploy/app.py` (no root `app.py`). Convergence docs live in GitHub `docs/`; the README points at the absolute GitHub URL so the Hub artifact does not 404 a relative `docs/` path.
