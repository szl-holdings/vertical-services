# Deployment contract — SZLHOLDINGS/vertical-services

The combined runtime is published only by `.github/workflows/hf-space.yml` from the exact current `main` commit.

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
