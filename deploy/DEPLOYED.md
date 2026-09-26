# Deployment contract — SZLHOLDINGS/vertical-services

The combined runtime can reach the Space through either of two writers defined in source (see [Publish paths](#publish-paths)). This file describes those paths. It is not a deployment receipt: `/api/build-info` on the running Space is the only deployment evidence.

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

Do not treat this file as a live occupancy receipt. `/api/build-info` is the canonical runtime record; `/api/source` and `/.well-known/szl-source.json` preserve the same identity tuple for compatibility. Brand on the landing page renders `VERSION` from `szl_verticals.core` (currently `2.2.0`).

## Publish paths

Both writers commit through the same pinned controller: `.github/scripts/hf_deploy_from_dockerfile.py` from `szl-holdings/.github` at `c889276e51e7d954c4bba8b216f86fc7577721fa`. It derives the Space file set from the `deploy/Dockerfile` COPY sources. Both writers run it with `--require-default-branch-tip`, so it refuses a revision that is not the current default-branch tip. It commits with the message `deploy(hf): sync szl-holdings/vertical-services@<sha> derived COPY set`. Both writers produce the same message, so a Space commit alone does not show which one wrote it. The writer's workflow run and its artifacts do.

### 1. `.github/workflows/hf-space.yml` in this repository

Pull requests to `main` run the contract tests, the six-vertical matrix and the container smoke. They never publish.

After a push to `main`, or a manual dispatch on `main`, the `resolve-publisher` job checks whether any of the `HF_ORG_TOKEN`, `HF_ORG_TOKEN1`, `HF_TOKEN` or `HF_WRITE_TOKEN` secrets is available to this repository. It uploads a `publication-routing.json` receipt that records the chosen mode:

- `local` (a token is available): the job preserves or creates `SENTRA_SIGNING_KEY` without rotating an existing value. The `publish` job then publishes the exact `github.sha` through `reusable-hf-deploy.yml` at the same `.github` pin. That workflow binds `SZL_SOURCE_REVISION`, restarts the Space, attests the HF commit and the declared smoke routes, and uploads `hf-deploy-evidence`. A follow-up job checks the live `/api/build-info` identity and probes every required official source.
- `delegated` (no token): the `delegated-publication` job uploads a `delegated-publication.json` receipt that names the a11oy writer below and records `"deployment_claimed": false`. Nothing is published, and the live-probe job is skipped.

The mode depends on repository secrets, which the source cannot show. To see which mode a run took, read that run's `publication-routing.json`.

### 2. `szl-holdings/a11oy` `.github/workflows/hf-sync.yml`, job `publish-vertical-flagships`

This job runs only when someone manually dispatches it in a11oy with `publish_vertical_flagships: true` and an approved `vertical_plan_json`. It also needs a11oy's own `deploy` job and its exact-main ownership check to pass first. Its `scripts/hf_publish_vertical_flagships_v4.py` resolves the current `vertical-services` `main` SHA. It requires a successful `Python contract suite` check run (the job in this repository's `.github/workflows/ci.yml`) on that exact SHA, then publishes it through the controller above. Nothing in this repository triggers that dispatch. The run uploads `hf-vertical-flagships-<run_id>-<attempt>` as its receipt.

## Verifying what is deployed

Read `/api/build-info` on `https://szlholdings-vertical-services.hf.space`: `build.state` must be `OBSERVED` and `build.revision` must equal the expected `main` SHA. `python tools/verify_runtime_identity.py --base-url https://szlholdings-vertical-services.hf.space --expected-revision <sha>` runs that check, along with parity across the identity routes. None of these is a deployment receipt: a green workflow run, a `DELEGATED` receipt or a Space commit message.

The historical `SZLHOLDINGS/vessels` Space is retained. Vessels is consolidated into Killinchu as the public maritime surface, while the executable risk engine remains available at `/vessels` in this combined service.

The Space tree copies only `deploy/app.py` (no root `app.py`). Convergence docs live in GitHub `docs/`; the README points at the absolute GitHub URL so the Hub artifact does not 404 a relative `docs/` path.
