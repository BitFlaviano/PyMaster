FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYMASTER_DB=/app/pymaster.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY pyproject.toml ./

# Datasets CSV ja estao no repositorio (app/data/datasets)

EXPOSE 8000

CMD ["sh", "-c", "if [ -n \"$PYMASTER_UPLOADS_DIR\" ]; then mkdir -p \"$PYMASTER_UPLOADS_DIR\" /var/data/scratch; ln -sfn \"$PYMASTER_UPLOADS_DIR\" /app/app/static/uploads; fi; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]