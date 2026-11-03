# SPDX-License-Identifier: Apache-2.0
# Dependency-free Python runtime for the SZL Vertical Frontier.
# The base image is pinned by the immutable digest below.
FROM mirror.gcr.io/library/python:3.15-slim@sha256:8c13a3f37a6a5b71498228e902c4b9f51c1f7900d49fabf71f9a650c6120e0d0

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
