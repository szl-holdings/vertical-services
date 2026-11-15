# Exact Finance projection emitted by tools/export_finance_artifact.py.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SZL_FINANCE_ORIGIN=stooq
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --disable-pip-version-check --no-cache-dir --require-hashes -r requirements.txt \
    && python -m pip check
COPY app.py engine.py feed.py receipts.py runtime_identity.py ./
COPY static ./static
COPY source-binding.json Dockerfile ./
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin szl
USER szl
EXPOSE 7860
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860","--no-server-header"]
