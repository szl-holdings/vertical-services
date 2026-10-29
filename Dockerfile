# Per-service compatibility image without an immutable source witness.
# Canonical Finance builds use tools/export_finance_artifact.py and the exported
# services/finance/Dockerfile; the Space itself builds deploy/Dockerfile.
# The base image is pinned by the immutable digest below.
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170
ARG SERVICE
ENV SERVICE=${SERVICE} PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check
COPY services/${SERVICE}/ ./
EXPOSE 7860
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860"]
