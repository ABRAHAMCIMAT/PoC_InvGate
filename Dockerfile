FROM python:3.15-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY scripts ./scripts

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown appuser /app/data
USER appuser

ENV DATA_DIR=/app/data

EXPOSE 8000

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
