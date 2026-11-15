# Per-service compatibility image without an immutable source witness.
# Canonical Finance builds use tools/export_finance_artifact.py and the exported
# services/finance/Dockerfile; the Space itself builds deploy/Dockerfile.
# The base image is pinned by the immutable digest below.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
ARG SERVICE
ENV SERVICE=${SERVICE} PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt \
    && python -m pip check
COPY services/${SERVICE}/ ./
EXPOSE 7860
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860"]
