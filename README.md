# Forex Signal Agent

Forex Signal Agent — это асинхронное приложение на Python, предназначенное для автоматического мониторинга валютных пар на рынке Форекс и отправки торговых сигналов через Telegram-бота. Агент анализирует рыночные данные с использованием технических индикаторов (EMA, MACD, RSI, ADX) и отправляет уведомления о значимых событиях и торговых сигналах.

## 🚀 Features

- **Multi-timeframe Analysis**: Monitor multiple currency pairs across different timeframes simultaneously
- **Technical Indicators**: EMA20/50, MACD, RSI, ADX analysis with trend detection
- **Pivot Levels**: Classical pivot level detection and proximity alerts
- **Telegram Notifications**: Real-time alerts via Telegram bot
- **Duplicate Prevention**: Built-in cooldown system to prevent spam
- **Backtesting**: Historical analysis capability for signal validation
- **Async Processing**: Efficient concurrent processing of multiple pairs

## 📋 Prerequisites

- Python 3.11+
- TA-Lib library (for technical indicators)

## 🛠️ Installation

### Local Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd forex-signal-agent
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

### Docker Installation

1. Build and run with Docker Compose:
   ```bash
   docker-compose up -d --build
   ```

## ⚙️ Configuration

### Configuration File

Edit `config.yaml` to customize the agent:

```yaml
timezone: Europe/Moscow
pairs:
  - EUR_USD:X
  - GBP_USD:X
  - EUR_GBP:X
timeframes:
  - timeframe: "4h"
    poll_interval_seconds: 180
telegram:
  bot_token: ""  # Better set via TELEGRAM_BOT_TOKEN environment variable
  chat_id: ""    # Better set via TELEGRAM_CHAT_ID environment variable
  message_cooldown_minutes: 60
adx_threshold: 20.0
rsi_overbought: 70.0
rsi_oversold: 30.0
notify_hourly_summary: true
backtest:
  enabled: false
  lookback_bars: 1500
sqlite_path: ./data/cache.db
```

### Environment Variables

Override configuration with environment variables:

- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Telegram chat ID for notifications
- `SQLITE_PATH` - Path to SQLite database file

## 📊 Supported Indicators and Signals

### Trend Detection
- **EMA Cross**: EMA20 crossing EMA50 with ADX confirmation
- **ADX Strength**: Strong trend detection using ADX values

### Momentum Indicators
- **MACD Cross**: Bullish and bearish MACD/Signal line crosses
- **RSI Levels**: Overbought (>70) and oversold (<30) conditions

### Pivot Level Analysis
- **Classical Pivots**: S1-S3, P, R1-R3 levels from previous day
- **Proximity Detection**: Alerts when price approaches pivot levels

### Tick Analysis
- **Sharp Movements**: Detection of >0.1% price movements between candle and tick

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/ --cov-report=html

# Run specific test category
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
```

## 🔒 Security Best Practices

- Never commit Telegram bot tokens or other secrets to the repository
- Use environment variables for sensitive configuration
- Ensure proper access controls on deployment systems

## 🤖 Usage Examples

### Standard Monitoring
```bash
forex-signal-agent --config config.yaml
```

### Backtesting Mode
```bash
forex-signal-agent --config config.yaml --backtest
```

## 📈 Performance Considerations

- **API Limits**: Yahoo Finance has rate limits; adjust polling intervals accordingly
- **Memory Usage**: Large datasets for analysis will increase memory consumption
- **Processing Capacity**: Adjust the number of monitored pairs/timeframes based on system capacity

## 🚨 Troubleshooting

### Common Issues

1. **TA-Lib Installation**: If you encounter issues installing TA-Lib:
   ```bash
   # On macOS
   brew install ta-lib
   pip install TA-Lib
   
   # On Ubuntu
   sudo apt-get install libta-lib0-dev
   pip install TA-Lib
   ```

2. **Permission Errors**: Ensure the application has write access to the data and logs directories.

3. **Network Issues**: The application requires internet connectivity to fetch market data.

### Monitoring and Logging

- Check `logs/agent.log` for application logs
- Database operations are logged and can be monitored for performance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For support, please open an issue in the GitHub repository or contact us directly.