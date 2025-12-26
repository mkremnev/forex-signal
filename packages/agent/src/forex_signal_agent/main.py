from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Union

import pandas as pd

from .analysis import (
    EventType,
    MarketSentiment,
    MarketSentimentAggregator,
    ProbabilisticAnalyzer,
    ProbabilityWeights,
)
from .config import AppConfig, load_config
from .data_providers import BinanceProvider, YahooFinanceProvider
from .exceptions import AnalysisException, DataProviderException, NotificationException
from .logging_config import setup_logging
from .message_formatter import format_probability_signal, format_volatility_alert
from .sqlite_cache import Cache
from .telegram_notifier import TelegramNotifier

if TYPE_CHECKING:
    from .integration_manager import IntegrationManager

# Set up structured logging
setup_logging("INFO", "logs/agent.log")
logger = logging.getLogger(__name__)


def _timeframe_to_seconds(tf: str) -> int:
    mapping = {
        "1": 60,
        "5": 300,
        "15": 900,
        "30": 1800,
        "60": 3600,
        "1h": 3600,
        "4h": 14400,
        "D": 86400,
    }
    return mapping.get(tf, 300)


def _is_forex_market_open(now: datetime) -> bool:
    """
    Check if forex market is currently open.
    Forex market hours: Sunday 22:00 GMT to Friday 22:00 GMT

    Args:
        now: Current datetime in UTC timezone

    Returns:
        True if market is open, False otherwise
    """
    # Get day of week (0=Monday, 6=Sunday)
    weekday = now.weekday()
    hour = now.hour

    # Market is closed from Friday 22:00 GMT to Sunday 22:00 GMT
    if weekday == 5:  # Saturday
        return False
    elif weekday == 6:  # Sunday
        return hour >= 22  # Open from 22:00 GMT onwards
    elif weekday == 4:  # Friday
        return hour < 22  # Closed after 22:00 GMT
    else:  # Monday to Thursday
        return True


async def fetch_candles(
    client: Union[YahooFinanceProvider, BinanceProvider],
    symbol: str,
    timeframe: str,
    bars: int = 400,
) -> pd.DataFrame:
    """Fetch OHLCV candles using data provider.

    Args:
        client: Data provider instance (YahooFinanceProvider or BinanceProvider)
        symbol: Trading symbol (e.g., "EURUSD=X" for forex, "BTCUSDT" for crypto)
        timeframe: Timeframe string (e.g., "1h", "4h", "1d")
        bars: Number of bars to fetch

    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    return await client.get_candles(symbol, timeframe, bars)


def daily_from_intraday(df: pd.DataFrame) -> pd.DataFrame:
    """Resample intraday data to daily OHLCV.

    Args:
        df: DataFrame with columns: open, high, low, close, volume

    Returns:
        Daily OHLCV DataFrame
    """
    if df.empty:
        return df
    daily = pd.DataFrame(
        {
            "open": df["open"].resample("1D").first(),
            "high": df["high"].resample("1D").max(),
            "low": df["low"].resample("1D").min(),
            "close": df["close"].resample("1D").last(),
            "volume": df["volume"].resample("1D").sum(),
        }
    ).dropna()
    return daily


async def process_pair_probabilistic(
    cfg: AppConfig,
    cache: Cache,
    notifier: TelegramNotifier,
    client: Union[YahooFinanceProvider, BinanceProvider],
    analyzer: ProbabilisticAnalyzer,
    symbol: str,
    timeframe: str,
    integration: Optional["IntegrationManager"] = None,
    market_sentiment: Optional[MarketSentiment] = None,
):
    """Process a single pair (forex or crypto) using probabilistic analysis."""
    try:
        logger.info(f"🔄 Probabilistic processing for {symbol} {timeframe}")

        # Fetch candles (already has columns: open, high, low, close, volume)
        candles = await fetch_candles(client, symbol, timeframe, bars=600)
        if candles.empty:
            logger.warning(f"No data returned for {symbol} on {timeframe}")
            return

        # Run probabilistic analysis with market sentiment context
        result = analyzer.analyze(candles, symbol, timeframe, market_sentiment)

        # Process events
        cooldown_sec = cfg.telegram.message_cooldown_minutes * 60
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())

        for event in result.events:
            # Determine kind and format message based on event type
            if event.event_type == EventType.PROBABILITY_SIGNAL:
                direction = event.data.get("direction", "consolidation")
                kind = f"prob_{direction}"
                message = format_probability_signal(event)

                # Publish to Redis for probability signals
                if integration is not None:
                    try:
                        volatility_regime = None
                        atr_percent = None
                        if result.volatility:
                            volatility_regime = result.volatility.regime.value
                            atr_percent = result.volatility.atr_percent

                        await integration.publish_probability_signal(
                            symbol=symbol,
                            timeframe=timeframe,
                            direction=direction,
                            probabilities=event.data.get("probabilities", {}),
                            confidence=event.data.get("confidence", 0.0),
                            is_actionable=event.data.get("is_actionable", False),
                            importance=event.importance,
                            factors=event.data.get("factors", {}),
                            volatility_regime=volatility_regime,
                            atr_percent=atr_percent,
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to publish probability signal to Redis: {e}"
                        )

            elif event.event_type == EventType.VOLATILITY_ALERT:
                regime = event.data.get("regime", "normal")
                kind = f"vol_{regime}"
                message = format_volatility_alert(event)
            else:
                # Unknown event type, skip
                continue

            # Telegram cooldown logic
            last_ts = await cache.get_last_sent(symbol, timeframe, kind)
            time_diff = now_ts - (last_ts or 0)
            cooldown_met = last_ts is None or time_diff >= cooldown_sec
            importance_check = event.importance >= 2
            should_send = cooldown_met or importance_check

            logger.debug(
                f"Cooldown check for {symbol} {timeframe} {kind}: "
                f"cooldown_met={cooldown_met}, importance={event.importance}, "
                f"should_send={should_send}"
            )

            if should_send:
                logger.info(
                    f"Sending probabilistic message for {symbol} {timeframe} {kind}"
                )
                await notifier.send_message(message)
                await cache.set_last_sent(symbol, timeframe, kind, now_ts)
            else:
                logger.info(
                    f"Message skipped for {symbol} {timeframe} {kind} (cooldown)"
                )

    except DataProviderException as e:
        logger.error(f"Data provider error for {symbol} {timeframe}: {e}")
        await notifier.send_message(
            f"⚠️ Ошибка получения данных {symbol} {timeframe}: {e}"
        )
    except AnalysisException as e:
        logger.error(f"Analysis error for {symbol} {timeframe}: {e}")
        await notifier.send_message(f"⚠️ Ошибка анализа {symbol} {timeframe}: {e}")
    except NotificationException as e:
        logger.error(f"Notification error for {symbol} {timeframe}: {e}")
    except Exception as e:
        logger.error(
            f"Unexpected error in probabilistic processing {symbol} {timeframe}: {e}"
        )
        await notifier.send_message(
            f"⚠️ Непредвиденная ошибка обработки {symbol} {timeframe}: {e}"
        )


async def hourly_summary(cfg: AppConfig, notifier: TelegramNotifier, cache: Cache):
    # to avoid duplicates, use meta key
    now = datetime.now(tz=timezone.utc)
    hour_key = now.strftime("%Y-%m-%dT%H")
    already = await cache.get_meta("last_hourly")
    if already == hour_key:
        return
    await notifier.send_message("🕒 Ежечасная проверка агента: всё работает.")
    await cache.set_meta("last_hourly", hour_key)


class Application:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Optional[AppConfig] = None
        self.cache: Optional[Cache] = None
        self.notifier: Optional[TelegramNotifier] = None
        self.client: Optional[YahooFinanceProvider] = None
        self.crypto_client: Optional[BinanceProvider] = None
        self.running = False
        self.paused = False  # For pause/resume commands from Dashboard
        self.integration: Optional[IntegrationManager] = None
        self.probabilistic_analyzer: Optional[ProbabilisticAnalyzer] = None
        self.sentiment_aggregator: Optional[MarketSentimentAggregator] = None
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize all components"""
        try:
            self.config = load_config(self.config_path)

            self.logger.info(f"Initializing cache with path: {self.config.sqlite_path}")
            self.cache = Cache(self.config.sqlite_path)
            await self.cache.init()

            self.notifier = TelegramNotifier(
                self.config.telegram.bot_token, self.config.telegram.chat_id
            )
            self.client = YahooFinanceProvider()

            # Initialize crypto provider if enabled
            if self.config.crypto.enabled:
                self.crypto_client = BinanceProvider(sandbox=self.config.crypto.sandbox)
                self.logger.info(
                    f"Crypto provider initialized (sandbox={self.config.crypto.sandbox})",
                    extra={"event_type": "crypto_init"},
                )

            # Initialize Redis integration if enabled
            if self.config.redis.enabled:
                from .integration_manager import IntegrationManager

                self.integration = IntegrationManager(self, self.config.redis)
                await self.integration.start()
                self.logger.info(
                    "Redis integration initialized", extra={"event_type": "redis_init"}
                )

            # Initialize probabilistic analyzer (always required)
            forex_weights = self.config.probability.forex_weights
            weights = ProbabilityWeights(
                roc=forex_weights.get("roc", 0.33),
                volatility=forex_weights.get("volatility", 0.33),
                volume=0.0,  # Volume not used for Forex
                correlation=forex_weights.get("correlation", 0.33),
            )
            self.probabilistic_analyzer = ProbabilisticAnalyzer(
                correlation_lookback_hours=self.config.correlation.lookback_hours,
                correlation_min_points=self.config.correlation.min_data_points,
                high_correlation_threshold=self.config.correlation.high_correlation_threshold,
                atr_period=self.config.volatility.atr_period,
                consolidation_threshold=self.config.volatility.consolidation_threshold,
                probability_weights=weights,
            )
            self.logger.info(
                "Probabilistic analyzer initialized",
                extra={"event_type": "probabilistic_analyzer_init"},
            )

            # Initialize sentiment aggregator if enabled
            if self.config.sentiment.enabled:
                self.sentiment_aggregator = MarketSentimentAggregator(
                    roc_lookback=self.config.sentiment.roc_lookback,
                    atr_period=self.config.volatility.atr_period,
                    risk_assets=self.config.sentiment.risk_assets,
                    safe_haven_assets=self.config.sentiment.safe_haven_assets,
                )
                self.logger.info(
                    "Market sentiment aggregator initialized",
                    extra={"event_type": "sentiment_aggregator_init"},
                )

            self.logger.info(
                "Application initialized successfully", extra={"event_type": "app_init"}
            )
        except Exception as e:
            self.logger.error(
                f"Failed to initialize application: {e}",
                extra={"event_type": "init_error"},
            )
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            # Stop Redis integration first
            if self.integration:
                await self.integration.stop()
                self.logger.info(
                    "Redis integration stopped", extra={"event_type": "redis_cleanup"}
                )

            if self.client:
                await self.client.close()
            if self.crypto_client:
                await self.crypto_client.close()
            if self.notifier:
                await self.notifier.close()
            self.logger.info(
                "Application cleaned up successfully",
                extra={"event_type": "app_cleanup"},
            )
        except Exception as e:
            self.logger.error(
                f"Error during cleanup: {e}", extra={"event_type": "cleanup_error"}
            )

    def pause(self) -> None:
        """Pause agent processing (called from Redis command)."""
        self.paused = True
        self.logger.info(
            "Agent paused via command", extra={"event_type": "agent_paused"}
        )

    def resume(self) -> None:
        """Resume agent processing (called from Redis command)."""
        self.paused = False
        self.logger.info(
            "Agent resumed via command", extra={"event_type": "agent_resumed"}
        )

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(
            f"Received signal {signum}, shutting down gracefully",
            extra={"event_type": "shutdown_signal", "signal": signum},
        )
        self.running = False

    async def run(self):
        """Main application loop"""
        self.running = True
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            while self.running:
                start_time = datetime.now()
                try:
                    await self._run_cycle()
                    cycle_duration = (datetime.now() - start_time).total_seconds()
                    self.logger.info(
                        f"Cycle completed in {cycle_duration:.2f}s",
                        extra={
                            "event_type": "cycle_complete",
                            "duration": cycle_duration,
                        },
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error in main cycle: {e}", extra={"event_type": "cycle_error"}
                    )

                # Sleep until next poll considering execution time
                interval = (
                    min([t.poll_interval_seconds for t in self.config.timeframes])
                    if self.config.timeframes
                    else 60
                )
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_for = max(1, interval - int(elapsed))
                await asyncio.sleep(sleep_for)
        finally:
            await self.cleanup()

    async def _run_cycle(self):
        """Execute a single processing cycle"""
        start_loop = datetime.now(tz=timezone.utc)

        # Check if agent is paused
        if self.paused:
            self.logger.debug("Skipping cycle - agent is paused")
            return

        # Check if forex market is open (Sunday 22:00 GMT to Friday 22:00 GMT)
        if not _is_forex_market_open(start_loop):
            weekday = start_loop.weekday()
            hour = start_loop.hour
            self.logger.info(
                f"Skipping cycle - forex market closed (day {weekday}, hour {hour} GMT)",
                extra={
                    "event_type": "cycle_skipped",
                    "weekday": weekday,
                    "hour_gmt": hour,
                },
            )
            return

        # Probabilistic analyzer is always used (migration complete)
        if self.probabilistic_analyzer is None:
            self.logger.error("Probabilistic analyzer not initialized")
            return

        # Update correlations with both forex AND crypto data
        try:
            all_data: dict[str, pd.DataFrame] = {}

            # Fetch forex data
            for sym in self.config.pairs:
                candles = await fetch_candles(self.client, sym, "1h", bars=48)
                if not candles.empty:
                    all_data[sym] = candles

            # Fetch crypto data if enabled
            if self.crypto_client and self.config.crypto.enabled:
                for sym in self.config.crypto.pairs:
                    try:
                        candles = await self.crypto_client.get_candles(sym, "1h", bars=48)
                        if not candles.empty:
                            all_data[sym] = candles
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch crypto data for {sym}: {e}")

            if all_data:
                self.probabilistic_analyzer.update_correlations(all_data)
                self.logger.debug(
                    f"Updated correlations for {len(all_data)} symbols "
                    f"(forex: {len(self.config.pairs)}, crypto: {len(self.config.crypto.pairs) if self.config.crypto.enabled else 0})",
                    extra={"event_type": "correlations_updated"},
                )
        except Exception as e:
            self.logger.warning(f"Failed to update correlations: {e}")

        # Aggregate market sentiment BEFORE per-instrument analysis
        market_sentiment: Optional[MarketSentiment] = None
        if self.sentiment_aggregator and all_data:
            try:
                market_sentiment = self.sentiment_aggregator.aggregate(all_data)
                self.logger.info(
                    f"Market sentiment: {market_sentiment.risk_sentiment.value} "
                    f"(confidence={market_sentiment.confidence:.2%})",
                    extra={
                        "event_type": "market_sentiment",
                        "sentiment": market_sentiment.risk_sentiment.value,
                        "confidence": market_sentiment.confidence,
                        "dominant_factor": market_sentiment.dominant_factor,
                    },
                )
            except Exception as e:
                self.logger.warning(f"Failed to aggregate market sentiment: {e}")

        tasks: List[asyncio.Task] = []
        errors_count = 0

        # Process forex pairs
        for tf_job in self.config.timeframes:
            tf = tf_job.timeframe
            for sym in self.config.pairs:
                tasks.append(
                    asyncio.create_task(
                        process_pair_probabilistic(
                            self.config,
                            self.cache,
                            self.notifier,
                            self.client,
                            self.probabilistic_analyzer,
                            sym,
                            tf,
                            self.integration,
                            market_sentiment=market_sentiment,
                        )
                    )
                )

        # Process crypto pairs if enabled
        if self.crypto_client and self.config.crypto.enabled:
            for tf_job in self.config.timeframes:
                tf = tf_job.timeframe
                for sym in self.config.crypto.pairs:
                    tasks.append(
                        asyncio.create_task(
                            process_pair_probabilistic(
                                self.config,
                                self.cache,
                                self.notifier,
                                self.crypto_client,
                                self.probabilistic_analyzer,
                                sym,
                                tf,
                                self.integration,
                                market_sentiment=market_sentiment,
                            )
                        )
                    )

        if self.config.notify_hourly_summary and start_loop.minute == 0:
            tasks.append(
                asyncio.create_task(
                    hourly_summary(self.config, self.notifier, self.cache)
                )
            )

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Count errors
            for result in results:
                if isinstance(result, Exception):
                    errors_count += 1

        # Calculate cycle duration and publish metrics
        cycle_end = datetime.now(tz=timezone.utc)
        cycle_duration_ms = (cycle_end - start_loop).total_seconds() * 1000

        # Publish metrics to Dashboard via Redis
        if self.integration and self.config:
            pairs_count = len(self.config.pairs) * len(self.config.timeframes)
            await self.integration.publish_metrics(
                pairs_processed=pairs_count,
                cycle_duration_ms=cycle_duration_ms,
                errors_in_cycle=errors_count,
                active_pairs=self.config.pairs,
                active_timeframes=[tf.timeframe for tf in self.config.timeframes],
            )


async def run_agent(args):
    """Legacy function to maintain compatibility"""
    app = Application(args.config)
    await app.initialize()
    await app.run()


async def run_backtest(args):
    """Run backtesting using probabilistic analyzer."""
    cfg = load_config(args.config)
    client = YahooFinanceProvider()
    crypto_client = None

    # Initialize probabilistic analyzer
    forex_weights = cfg.probability.forex_weights
    weights = ProbabilityWeights(
        roc=forex_weights.get("roc", 0.33),
        volatility=forex_weights.get("volatility", 0.33),
        volume=0.0,
        correlation=forex_weights.get("correlation", 0.33),
    )
    analyzer = ProbabilisticAnalyzer(
        correlation_lookback_hours=cfg.correlation.lookback_hours,
        correlation_min_points=cfg.correlation.min_data_points,
        high_correlation_threshold=cfg.correlation.high_correlation_threshold,
        atr_period=cfg.volatility.atr_period,
        consolidation_threshold=cfg.volatility.consolidation_threshold,
        probability_weights=weights,
    )

    try:
        logger.info("Starting probabilistic backtesting", extra={"event_type": "backtest_start"})

        # Initialize crypto client if enabled
        if cfg.crypto.enabled:
            crypto_client = BinanceProvider(sandbox=cfg.crypto.sandbox)
            logger.info("Crypto provider initialized for backtest")

        # First, build correlation matrix with all data
        all_data: dict[str, pd.DataFrame] = {}

        # Fetch forex data for correlation
        for sym in cfg.pairs:
            df = await fetch_candles(client, sym, "1h", bars=48)
            if not df.empty:
                all_data[sym] = df

        # Fetch crypto data for correlation if enabled
        if crypto_client and cfg.crypto.enabled:
            for sym in cfg.crypto.pairs:
                try:
                    df = await crypto_client.get_candles(sym, "1h", bars=48)
                    if not df.empty:
                        all_data[sym] = df
                except Exception as e:
                    logger.warning(f"Failed to fetch crypto data for {sym}: {e}")

        if all_data:
            analyzer.update_correlations(all_data)
            logger.info(f"Built correlation matrix with {len(all_data)} symbols")

        # Run backtest for forex pairs
        for tf_job in cfg.timeframes:
            tf = tf_job.timeframe
            for sym in cfg.pairs:
                df = await fetch_candles(client, sym, tf, bars=cfg.backtest.lookback_bars)
                if df.empty:
                    logger.warning(f"No data for {sym} {tf}")
                    continue

                result = analyzer.analyze(df, sym, tf)

                logger.info(
                    f"Backtest {sym} {tf}: {len(result.events)} events, "
                    f"direction={result.probability.direction.value if result.probability else 'N/A'}, "
                    f"confidence={result.probability.confidence:.2%}" if result.probability else "",
                    extra={
                        "event_type": "backtest_results",
                        "symbol": sym,
                        "timeframe": tf,
                        "event_count": len(result.events),
                    },
                )

                for ev in result.events:
                    logger.info(
                        f" - [{ev.event_type.value}] {ev.data}",
                        extra={"event_type": "backtest_event", "symbol": sym},
                    )

        # Run backtest for crypto pairs if enabled
        if crypto_client and cfg.crypto.enabled:
            for tf_job in cfg.timeframes:
                tf = tf_job.timeframe
                for sym in cfg.crypto.pairs:
                    try:
                        df = await crypto_client.get_candles(sym, tf, bars=cfg.backtest.lookback_bars)
                        if df.empty:
                            logger.warning(f"No data for {sym} {tf}")
                            continue

                        result = analyzer.analyze(df, sym, tf)

                        logger.info(
                            f"Backtest {sym} {tf}: {len(result.events)} events, "
                            f"direction={result.probability.direction.value if result.probability else 'N/A'}, "
                            f"confidence={result.probability.confidence:.2%}" if result.probability else "",
                            extra={
                                "event_type": "backtest_results",
                                "symbol": sym,
                                "timeframe": tf,
                            },
                        )

                        for ev in result.events:
                            logger.info(
                                f" - [{ev.event_type.value}] {ev.data}",
                                extra={"event_type": "backtest_event", "symbol": sym},
                            )
                    except Exception as e:
                        logger.error(f"Error backtesting {sym}: {e}")

    except Exception as e:
        logger.error(f"Error during backtesting: {e}", extra={"event_type": "backtest_error"})
        raise
    finally:
        await client.close()
        if crypto_client:
            await crypto_client.close()
        logger.info("Backtesting completed", extra={"event_type": "backtest_complete"})


def main():
    """Main entry point with proper error handling"""
    logging.info("Starting Forex Signal Agent...")

    parser = argparse.ArgumentParser(description="Forex Signal Agent")
    parser.add_argument("--config", default="config.yaml", help="Путь к YAML конфигу")
    parser.add_argument(
        "--backtest", action="store_true", help="Запустить бэктест и выйти"
    )
    args = parser.parse_args()

    if args.backtest:
        logging.info("Starting Forex Signal Agent in backtest mode...")
        try:
            asyncio.run(run_backtest(args))
        except Exception as e:
            logger.error(f"Backtest error: {e}", extra={"event_type": "backtest_error"})
            sys.exit(1)
    else:
        logging.info("Starting Forex Signal Agent in normal mode...")
        try:
            asyncio.run(run_agent(args))
        except Exception as e:
            logger.error(f"Agent error: {e}", extra={"event_type": "agent_error"})
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Agent stopped by user", extra={"event_type": "agent_shutdown"})
    except Exception as e:
        logger.error(f"Unexpected error: {e}", extra={"event_type": "unexpected_error"})
        sys.exit(1)
