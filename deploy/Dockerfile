FROM python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt
COPY deploy/app.py ./app.py
COPY deploy/szl_verticals/ ./szl_verticals/
COPY deploy/source_revision.txt ./source_revision.txt
COPY contracts/fashion-lineage.v1.json ./contracts/fashion-lineage.v1.json
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin szl && chown -R szl:szl /app
USER szl
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=4).read()"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--no-server-header"]
