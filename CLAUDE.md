# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Forex Signal Agent is a monorepo project that combines:
- **Backend**: Asynchronous Python application that monitors forex currency pairs and sends trading signals via Telegram. It analyzes market data using technical indicators (EMA, MACD, RSI, ADX) and classical pivot levels, with built-in cooldown mechanisms to prevent notification spam.
- **Dashboard**: React-based web frontend for monitoring and configuration (located in `packages/dashboard/`)
- **Agent**: Python package for signal generation (located in `packages/agent/`)

### Monorepo Structure

The project uses a packages-based monorepo layout:
- `packages/agent/` - Core forex signal agent (Python)
- `packages/backend/` - Backend API services (Python)
- `packages/dashboard/` - Web dashboard (React + TypeScript)

## Development Commands

### Installation and Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (editable mode)
pip install -e .

# TA-Lib installation (required dependency)
# macOS:
brew install ta-lib
# Ubuntu:
sudo apt-get install libta-lib0-dev
```

### Running the Application
```bash
# Standard monitoring mode
forex-signal-agent --config config.yaml

# Backtesting mode
forex-signal-agent --config config.yaml --backtest

# Docker deployment
docker-compose up -d --build
```

### Testing
```bash
# Python tests
pytest

# Run with coverage
pytest --cov=src/ --cov-report=html

# Run specific test files (tests are in tests/ and root directory)
pytest tests/test_basic.py
pytest test_cache.py
pytest test_cache_detailed.py
```

### Dashboard Development
```bash
# Navigate to dashboard package
cd packages/dashboard

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## Architecture Overview

### Core Components

**Main Application (`src/forex_signal_agent/main.py`)**
- `Application` class manages application lifecycle with graceful shutdown
- `process_pair()` orchestrates data fetching, analysis, and notification
- Uses asyncio for concurrent processing of multiple pairs/timeframes
- Implements cooldown system via SQLite cache to prevent duplicate notifications

**Analyzer (`src/forex_signal_agent/analyzer.py`)**
- Modular analysis architecture with separate functions for each signal type
- `analyze_pair()` is the main entry point, returns list of `Event` objects
- Each event has `kind`, `message`, and `importance` (1=info, 2=important)
- Signal detection modules:
  - `_analyze_trend()`: EMA20/EMA50 cross with ADX confirmation
  - `_analyze_trend_continuation()`: Detects strengthening trends via ADX increase
  - `_analyze_macd_cross()`: MACD/signal line crossovers
  - `_analyze_rsi()`: Overbought/oversold conditions
  - `_analyze_pivot_levels()`: Classical pivot level proximity detection

**Data Management (`src/forex_signal_agent/data_manager.py`)**
- `DataFetchManager`: Implements caching to reduce API calls
- `batch_fetch_candles()`: Parallel fetching with deduplication
- Cache TTL is configurable (default 60 seconds)

**SQLite Cache (`src/forex_signal_agent/sqlite_cache.py`)**
- Two tables: `events` (notification timestamps) and `meta` (metadata)
- Cooldown logic: Checks if sufficient time has passed since last notification
- Important events (importance >= 2) bypass cooldown period

**Technical Indicators (`src/forex_signal_agent/indicators.py`)**
- Uses TA-Lib for all calculations
- Expects DataFrame with columns: `o`, `h`, `l`, `c`, `v` and DatetimeIndex (UTC)
- Returns DataFrame with added columns: `ema20`, `ema50`, `adx`, `macd`, `macd_signal`, `macd_hist`, `rsi`

**Data Providers**
- `yahoo_finance_client.py`: Yahoo Finance API client with 4h resampling support
- `alpha_vantage_client.py`: Alternative provider (not actively used)
- Timeframe mapping: "4h" -> "60m" with resampling

### Configuration System

**Configuration Loading (`src/forex_signal_agent/config.py`)**
- YAML-based with Pydantic validation
- Environment variables override YAML values
- Key settings: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SQLITE_PATH`

**Important Configuration Parameters**
- `message_cooldown_minutes`: Prevents duplicate notifications (default: 60)
- `adx_threshold`: Minimum ADX for trend confirmation (default: 20.0)
- `rsi_overbought/rsi_oversold`: RSI thresholds (default: 70/30)
- `backtest.lookback_bars`: Historical bars to analyze (default: 1500)

### Signal Importance System

The analyzer uses an importance system to prioritize signals:
- `importance=1`: Normal signals respect cooldown period
- `importance>=2`: Critical signals bypass cooldown, always sent
- Constants defined in `analyzer.py`: `TREND_IMPORTANCE`, `TREND_IMPORTANCE_STRENGTH`, `SIGNAL_IMPORTANCE`, `MAJOR_PIVOT_IMPORTANCE`, `MINOR_PIVOT_IMPORTANCE`

### Notification Flow

1. `process_pair()` fetches candles and runs analysis
2. For each event, checks cache for last sent timestamp
3. Calculates time difference and evaluates: `should_send = cooldown_met OR importance >= 2`
4. If sending, updates cache with current timestamp
5. Telegram notifications include timeframe suffix: `(TF: 4h)`

## Dashboard Frontend Architecture

### Tech Stack (as of November 2025)

**Core Framework**
- React 19.1.1 - Latest React version with concurrent features
- React Router DOM 7.9.5 - File-based routing with lazy loading
- TypeScript 5.9.3 - Type safety

**UI & Styling**
- Tailwind CSS 4.1.17 - Utility-first CSS framework with PostCSS integration
- Styled Components 6.1.19 - CSS-in-JS for component styling
- Radix UI 1.4.3 - Unstyled, accessible UI components
- @fontsource/roboto 5.2.8 - Self-hosted fonts

**Build Tools**
- Vite 7.1.7 - Fast build tool and dev server
- vite-tsconfig-paths 5.1.4 - Path aliasing support (`@/` imports)
- @vitejs/plugin-react 5.0.4 - React Fast Refresh support

**Code Quality**
- ESLint 9.36.0 with TypeScript support
- Prettier integration via eslint-plugin-prettier
- react-error-boundary 6.0.0 - Error boundary handling

### Project Structure

```
packages/dashboard/
├── src/
│   ├── app/
│   │   ├── routes/         # React Router configuration
│   │   │   └── index.ts    # Route definitions with lazy loading
│   │   └── theme/          # Global theme and styles
│   │       └── index.css   # Global CSS
│   ├── pages/              # Page components (lazy loaded)
│   │   ├── dashboard/      # Main dashboard page
│   │   ├── settings/       # Settings page
│   │   └── not-found/      # 404 page
│   ├── widgets/            # Complex reusable components
│   │   └── layout/         # App layout with navigation
│   ├── App.tsx             # Root component
│   └── main.tsx            # Application entry point
├── public/                 # Static assets
├── index.html              # HTML entry point
├── vite.config.ts          # Vite configuration
├── tailwind.config.js      # Tailwind CSS configuration
├── postcss.config.js       # PostCSS configuration
├── tsconfig.json           # TypeScript configuration
└── tsconfig.alias.json     # Path alias configuration
```

### Key Architectural Decisions

**1. Route-Based Code Splitting**
- Routes use React Router's lazy loading pattern
- Each page is loaded on-demand to reduce initial bundle size
- Hot module replacement (HMR) enabled for development

**2. Path Aliasing**
- `@/` prefix maps to `src/` directory
- Configured via `vite-tsconfig-paths` plugin
- Simplifies imports: `import Layout from "@/widgets/layout"`

**3. Hybrid Styling Approach**
- Tailwind CSS for utility classes (navigation, layout)
- Styled Components for complex component-specific styles
- Global theme defined in `src/app/theme/index.css`

**4. Layout Pattern**
- Root layout component with navigation menu
- Uses React Router's `<Outlet />` for nested routes
- Suspense boundaries with loading fallbacks

**5. Development Experience**
- Hot module replacement with route disposal on hot reload
- TypeScript strict mode enabled
- ESLint + Prettier for code formatting
- Vite dev server with fast refresh

### Component Guidelines

**Pages** (`src/pages/`)
- Exported as named export `Page`
- Lazy loaded via React Router
- Should be lightweight containers

**Widgets** (`src/widgets/`)
- Complex, reusable components
- May contain business logic
- Example: Layout component with navigation

**Navigation**
- Fixed top navigation using Radix UI NavigationMenu
- Russian language UI ("Дашбоард", "Настройки")
- Styled with Tailwind utilities and shadow effects

### Configuration Files

**vite.config.ts**
- Base path: `/`
- Plugins: Tailwind CSS, React, TypeScript paths
- Configured for optimal development experience

**tailwind.config.js**
- Tailwind v4 configuration
- PostCSS integration via `@tailwindcss/vite`

**tsconfig.alias.json**
- Path mappings for `@/*` imports
- Enables clean import statements

### Recent Updates (November 2025)

- Upgraded to React 19.1.1 with latest concurrent features
- Updated to Vite 7.1.7 for improved build performance
- Integrated Tailwind CSS 4.1.17 with native PostCSS support
- Added Prettier configuration for consistent code formatting
- Implemented file-based routing with lazy loading
- Added error boundaries for graceful error handling
- Configured path aliases for cleaner imports

## Working with the Codebase

### Adding New Indicators

1. Add calculation to `compute_indicators()` in `indicators.py`
2. Create analysis function in `analyzer.py` following pattern: `_analyze_<name>()`
3. Add to `analyze_pair()` event aggregation
4. Define importance level constant at top of `analyzer.py`

### Modifying Signal Logic

- All signal detection is in `analyzer.py` with separate functions
- Each function returns `List[Event]` for modularity
- Constants at top of file control thresholds and importance levels
- Cooldown logic is in `main.py:process_pair()`, not in analyzer

### Error Handling

- Custom exceptions in `exceptions.py`: `DataProviderException`, `AnalysisException`, `NotificationException`
- `process_pair()` catches and handles exceptions per-pair to prevent cascade failures
- Structured logging with `event_type` extra field for filtering

### Testing Considerations

- Test files exist in both `tests/` and root directory
- Tests for cache behavior: `test_cache.py`, `test_cache_detailed.py`
- Tests for app initialization: `test_app_init.py`
- Use backtesting mode to validate signals without Telegram notifications

## Important Patterns

### Async/Await Usage
- All I/O operations (API calls, database, Telegram) are async
- Use `asyncio.gather()` for concurrent task execution
- Cache operations use `asyncio.Lock` for thread safety

### DataFrame Conventions
- Column names: lowercase single letters (`o`, `h`, `l`, `c`, `v`)
- Index must be DatetimeIndex in UTC timezone
- All price data converted to float64 for TA-Lib compatibility

### Retry Mechanisms
- Uses `tenacity` library for retry logic
- Implemented in `retry_utils.py` for flaky API calls

### Logging
- Structured logging setup in `logging_config.py`
- Use `extra={'event_type': 'xyz'}` for categorization
- Log levels: INFO for normal operations, DEBUG for cache/cooldown details