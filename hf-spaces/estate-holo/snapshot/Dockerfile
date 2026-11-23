# SZL Live Estate Hologram - Hugging Face Space. Stdlib HTTP only.
FROM mirror.gcr.io/library/python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
COPY app.py ./app.py
COPY index.html ./index.html
EXPOSE 7860
CMD ["python", "-u", "app.py"]
