# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install project
COPY pyproject.toml /app/
COPY src /app/src
COPY config.yaml /app/config.yaml
COPY agent.log /app/logs/agent.log

RUN pip install --upgrade pip \
    && pip install .

# Create data dir for sqlite
RUN mkdir -p /app/data \
    && useradd -m appuser \
    && chown -R appuser:appuser /app

USER appuser

CMD ["forex-signal-agent", "--config", "/app/config.yaml"]
