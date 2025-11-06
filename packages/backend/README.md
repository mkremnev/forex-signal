# Forex Backend API

FastAPI-based backend service for the Forex Signal Agent dashboard.

## Features

- RESTful API for signal management
- PostgreSQL database with SQLAlchemy ORM
- Redis caching and session management
- JWT authentication
- WebSocket support for real-time updates

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Development mode with auto-reload
forex-backend

# Or with uvicorn directly
uvicorn forex_backend.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

See root README.md for development setup instructions.