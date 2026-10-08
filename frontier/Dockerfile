# SPDX-License-Identifier: Apache-2.0
# Dependency-free Python 3.12 runtime for the SZL Vertical Frontier.
# Digest-pinned OCI index for python:3.12-slim (3.12.14-slim-trixie, linux/amd64
# included), identical on mirror.gcr.io and registry-1.docker.io on 2026-09-29.
FROM mirror.gcr.io/library/python:3.14-slim@sha256:c3e521df8b2b498a7a682e7e18676771cb80c6b75b8699af886b2d554ce40151

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=7860

WORKDIR /app

RUN groupadd --system --gid 10001 szl \
    && useradd --system --uid 10001 --gid szl --home-dir /nonexistent --shell /usr/sbin/nologin szl

COPY --chown=szl:szl app.py ./app.py
COPY --chown=szl:szl verticals.json ./verticals.json
COPY --chown=szl:szl static ./static

RUN python -I -P app.py --self-test

USER 10001:10001
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=4 \
  CMD python -c "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=4)); assert data['ok'] is True"

CMD ["python", "-I", "-P", "app.py"]
