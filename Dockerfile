FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend PANMAN_DATA_ROOT=/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin libreoffice-writer libreoffice-calc libreoffice-impress && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend /app/backend
COPY frontend /app/frontend
RUN PYTHONPATH=/app/backend:/app/frontend python -c "import config; from avatar_renderer import avatar_asset_manifest; avatar_asset_manifest(config.AVATAR_MODEL_FILE)"
EXPOSE 8000
CMD ["uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--ws-max-size", "15000000"]
