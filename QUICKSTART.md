# Quick Start Guide

This guide will help you get the Forex Signal Agent monorepo up and running quickly.

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for dashboard development)
- TA-Lib library (for agent)

## Quick Start with Docker (Recommended)

### 1. Clone and Configure

```bash
git clone <repository-url>
cd forex-signal-agent
```

### 2. Set Up Environment Variables

Create a `.env` file in the root directory:

```bash
cat > .env << 'EOF'
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# User IDs for Docker (optional, defaults to root)
USER_UID=1000
USER_GID=1000
EOF
```

### 3. Start All Services

```bash
docker-compose up -d --build
```

This will start:
- PostgreSQL database (port 5432)
- Redis cache (port 6379)
- Backend API (port 8000)
- Dashboard (port 5173)
- Agent service

### 4. Verify Services

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Check specific service
docker-compose logs -f backend
```

### 5. Access the Application

- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/api/v1/health
- **Dashboard**: http://localhost:5173

### 6. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes data)
docker-compose down -v
```

## Local Development Setup

### Option 1: Agent Only

If you only want to run the signal agent locally:

```bash
cd packages/agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install TA-Lib (macOS)
brew install ta-lib

# Install TA-Lib (Ubuntu)
sudo apt-get install libta-lib0-dev

# Install package
pip install -e .

# Configure
cp config.yaml.example config.yaml
# Edit config.yaml with your settings

# Run
forex-signal-agent --config config.yaml
```

### Option 2: Backend Development

```bash
cd packages/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install package
pip install -e .

# Start PostgreSQL and Redis (via Docker)
docker-compose up -d postgres redis

# Run backend
uvicorn forex_backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Dashboard Development

```bash
cd packages/dashboard

# Install dependencies
npm install

# Start development server
npm run dev

# Dashboard will be available at http://localhost:5173
```

### Option 4: Full Stack Development

Terminal 1 - Infrastructure:
```bash
docker-compose up postgres redis
```

Terminal 2 - Backend:
```bash
cd packages/backend
source .venv/bin/activate
uvicorn forex_backend.main:app --reload
```

Terminal 3 - Dashboard:
```bash
cd packages/dashboard
npm run dev
```

Terminal 4 - Agent:
```bash
cd packages/agent
source .venv/bin/activate
forex-signal-agent --config config.yaml
```

## Testing

### Agent Tests
```bash
cd packages/agent
pytest
pytest --cov=src/ --cov-report=html
```

### Backend Tests
```bash
cd packages/backend
pytest
```

### Dashboard Tests
```bash
cd packages/dashboard
npm test
```

## Common Tasks

### View Backend Logs
```bash
docker-compose logs -f backend
```

### View Agent Logs
```bash
docker-compose logs -f agent
# Or local file
tail -f logs/agent.log
```

### Access Database
```bash
# Via docker-compose
docker-compose exec postgres psql -U forex -d forex_db

# Or locally
psql -h localhost -U forex -d forex_db
```

### Access Redis CLI
```bash
docker-compose exec redis redis-cli
```

### Rebuild Specific Service
```bash
# Rebuild and restart backend
docker-compose up -d --build backend

# Rebuild all
docker-compose build --no-cache
```

### Reset Database
```bash
# Stop services
docker-compose down

# Remove volumes
docker volume rm forex-signal-agent_postgres_data
docker volume rm forex-signal-agent_redis_data

# Start fresh
docker-compose up -d
```

## Configuration

### Agent Configuration

Edit `packages/agent/config.yaml`:

```yaml
timezone: Europe/Moscow
pairs:
  - EUR_USD:X
  - GBP_USD:X
timeframes:
  - timeframe: "4h"
    poll_interval_seconds: 180
telegram:
  bot_token: ""  # Use TELEGRAM_BOT_TOKEN env var
  chat_id: ""    # Use TELEGRAM_CHAT_ID env var
  message_cooldown_minutes: 60
adx_threshold: 20.0
rsi_overbought: 70.0
rsi_oversold: 30.0
```

### Backend Configuration

Environment variables in `.env`:

```bash
DATABASE_URL=postgresql+asyncpg://forex:forex@localhost:5432/forex_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
DEBUG=True
```

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 8000
lsof -i :8000

# Change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 externally
```

### Database Connection Issues

```bash
# Check postgres is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres pg_isready -U forex
```

### Agent Not Receiving Data

1. Check API rate limits
2. Verify internet connectivity
3. Check logs for errors: `docker-compose logs agent`
4. Verify Telegram credentials in `.env`

### Dashboard Not Loading

```bash
# Check backend is running
curl http://localhost:8000/api/v1/health

# Check dashboard container
docker-compose logs dashboard

# Rebuild dashboard
docker-compose up -d --build dashboard
```

## Next Steps

1. **Explore API**: Visit http://localhost:8000/docs
2. **Configure Agent**: Edit `packages/agent/config.yaml`
3. **Set Up Telegram**: Get bot token from @BotFather
4. **Monitor Signals**: Check dashboard or Telegram notifications
5. **Review Code**: Start with `packages/agent/src/forex_signal_agent/main.py`

## Support

- Check `README.md` for detailed documentation
- Review `tasks/implementation-plan.md` for development roadmap
- Open issues on GitHub for bugs or questions

## Useful Commands Cheat Sheet

```bash
# Start all services
docker-compose up -d

# View all logs
docker-compose logs -f

# Restart a service
docker-compose restart backend

# Execute command in container
docker-compose exec backend /bin/sh

# Scale a service
docker-compose up -d --scale agent=3

# Clean up everything
docker-compose down -v --remove-orphans

# Check service health
curl http://localhost:8000/api/v1/health
```

Happy trading! 🚀📈