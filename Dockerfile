# Standalone per-service image (CI: "Build and exercise standalone finance runtime";
# services/finance/README.md). The Space itself builds deploy/Dockerfile.
# Digest-pinned OCI index for python:3.12-slim (3.12.14-slim-trixie), the same
# index frontier/Dockerfile pins.
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170
ARG SERVICE
ENV SERVICE=${SERVICE} PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/${SERVICE}/ ./
EXPOSE 7860
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860"]
