# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    tzdata \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install package
COPY pyproject.toml /app/
COPY src /app/src

RUN pip install --upgrade pip \
    && pip install .

# Create logs directory
RUN mkdir -p /app/logs && chmod 777 /app/logs

EXPOSE 8000

CMD ["uvicorn", "forex_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]