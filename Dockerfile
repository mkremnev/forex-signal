# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow

ARG user_uid=1000
ARG user_gid=1000

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

RUN pip install --upgrade pip \
    && pip install .

# Create user/group and set ownership based on the provided UID/GID
RUN if [ ${user_uid} -ne 0 ]; then \
        groupadd -g $user_gid appuser && \
        useradd -u $user_uid -g $user_gid -m -s /bin/sh appuser && \
        mkdir -p /app/data /app/logs && \
        chown -R appuser:appuser /app; \
    else \
        # When running as root (UID 0), keep ownership as root but ensure directories are writable
        mkdir -p /app/data /app/logs && \
        chown -R root:root /app && \
        chmod -R 777 /app/data /app/logs; \
    fi

# Set the user based on whether we're using root or not
USER ${user_uid}

CMD ["forex-signal-agent", "--config", "/app/config.yaml"]
