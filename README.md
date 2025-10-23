### Forex Signal Agent

Асинхронный агент-оповещатель по форекс-парам: получает OHLCV данные из Finnhub, анализирует индикаторы (EMA20/50, ADX, MACD, RSI), уровни классических пивотов и отправляет уведомления в Telegram. Не является торговым советником — сообщает о «движении» на рынке.

Стек: Python, asyncio, Pandas, TA-Lib, httpx, SQLite (кеш), Docker, docker-compose.

#### Возможности
- Периодический опрос по заданным таймфреймам и парам.
- Индикаторы: EMA(20/50), ADX(14), MACD(12,26,9), RSI(14).
- Классические пивоты (уровни от предыдущего дня) и уведомления при касании.
- Антиспам: не чаще N минут на событие/пару/таймфрейм (по умолчанию 60 минут), важные события проходят вне очереди.
- Ежечасный «heartbeat» (настраивается).
- Бэктест режима: анализ истории без отправки в Telegram.

#### Конфигурация
Скопируйте и отредактируйте config.yaml. Основные параметры:
- timezone: Europe/Moscow
- pairs: список символов Finnhub для форекса, например OANDA:EUR_USD
- timeframes: список заданий {timeframe: "5", poll_interval_seconds: 60}
- telegram: bot_token, chat_id, message_cooldown_minutes
- finnhub: api_key (лучше задавать через переменные окружения)
- пороги ADX и RSI, включение бэктеста, путь к SQLite

Переменные окружения приоритетнее:
- FINNHUB_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- SQLITE_PATH

#### Локальный запуск (без Docker)
1) Python 3.11+
2) Установите зависимости: `pip install .`
3) Запуск агента:
```
forex-signal-agent --config config.yaml
```
4) Бэктест:
```
forex-signal-agent --config config.yaml --backtest
```

#### Docker
Собрать и запустить через docker-compose:
```
export FINNHUB_API_KEY=... \
       TELEGRAM_BOT_TOKEN=... \
       TELEGRAM_CHAT_ID=... 

docker compose up -d --build
```
Логи:
```
docker compose logs -f
```

#### Примечания
- Для символов используйте формат Finnhub форекса (например, OANDA:EUR_USD).
- Таймфреймы поддерживаются: 1,5,15,30,60,1h,4h,D (4h формируется ресемплингом из 60m).
- Finnhub лимитирует частоту запросов — подберите poll_interval_seconds соответственно вашему тарифу.
- TA-Lib устанавливается из PyPI (доступны колеса для Linux). В Docker образе используется python:3.11-slim.

#### Безопасность
Не храните токены в репозитории. Для секретов используйте переменные окружения или внешние секреты в Docker/Orchestrator.
