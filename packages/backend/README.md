# Forex Backend API

FastAPI-based backend service for the Forex Signal Agent dashboard.

## Features

- RESTful API for settings management and authentication
- PostgreSQL database with SQLAlchemy ORM (async)
- Redis pub/sub for hot-reload configuration
- JWT authentication
- Hybrid settings storage (global + user overrides)
- Alembic database migrations

## Installation

```bash
# Install dependencies with uv
uv pip install -e .

# Or with pip
pip install -e .
```

## Database Setup

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your database credentials

3. Run database migrations:
```bash
# Apply migrations
alembic upgrade head

# Seed initial settings
python -m forex_backend.db.seed
```

## Usage

```bash
# Development mode with auto-reload
forex-backend

# Or with uvicorn directly
uvicorn forex_backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Database Migrations

```bash
# Create a new migration (after modifying models)
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Project Structure

```
packages/backend/
├── alembic/                  # Database migrations
│   └── versions/            # Migration files
├── src/
│   └── forex_backend/
│       ├── api/             # API endpoints
│       │   └── v1/          # API v1 routes
│       ├── db/              # Database configuration
│       │   ├── database.py  # SQLAlchemy setup
│       │   └── seed.py      # Seed script
│       ├── models/          # SQLAlchemy models
│       │   ├── user.py      # User model
│       │   └── setting.py   # Settings models
│       ├── schemas/         # Pydantic schemas
│       ├── services/        # Business logic
│       ├── config.py        # Application config
│       └── main.py          # FastAPI app
├── alembic.ini              # Alembic configuration
├── .env.example             # Environment variables template
├── pyproject.toml           # Project dependencies
└── README.md                # This file
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

See root README.md for development setup instructions.