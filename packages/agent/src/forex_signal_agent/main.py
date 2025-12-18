from __future__ import annotations
import logging
import argparse
import asyncio
import signal
import sys
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from contextlib import asynccontextmanager

import pandas as pd

from .config import load_config, AppConfig
from .yahoo_finance_client import YahooFinanceClient, YAHOO_TIMEFRAME_MAP
from .telegram_notifier import TelegramNotifier
from .sqlite_cache import Cache
from .analyzer import analyze_pair, Event
from .exceptions import DataProviderException, AnalysisException, NotificationException
from .logging_config import setup_logging

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


async def fetch_candles(client: YahooFinanceClient, symbol: str, timeframe: str, bars: int = 400) -> pd.DataFrame:
    now = int(datetime.now(tz=timezone.utc).timestamp())
    sec = _timeframe_to_seconds(timeframe)
    start = now - sec * (bars + 5)

    resolution = YAHOO_TIMEFRAME_MAP.get(timeframe, timeframe)
    df = await client.get_forex_candles(symbol, resolution, start, now)
    if timeframe == "4h" and resolution == "60m":
        df = YahooFinanceClient.resample_to_4h(df)
    return df


def daily_from_intraday(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    daily = pd.DataFrame({
        "o": df["o"].resample("1D").first(),
        "h": df["h"].resample("1D").max(),
        "l": df["l"].resample("1D").min(),
        "c": df["c"].resample("1D").last(),
        "v": df["v"].resample("1D").sum(),
    }).dropna()
    return daily


async def process_pair(cfg: AppConfig, cache: Cache, notifier: TelegramNotifier, client: YahooFinanceClient, symbol: str, timeframe: str, integration: Optional['IntegrationManager'] = None):
    """Process a single pair with comprehensive error handling"""
    try:
        logger.info(f"🔄 Обработка пары {symbol} {timeframe}")
        
        candles = await fetch_candles(client, symbol, timeframe, bars=600)
        if candles.empty:
            logger.warning(f"No data returned for {symbol} on {timeframe}")
            return
            
        daily = daily_from_intraday(candles)
        events = analyze_pair(candles, daily, symbol, cfg.adx_threshold, cfg.rsi_overbought, cfg.rsi_oversold)
        
        # Дополнительно: тиковое движение относительно последнего закрытия свечи
        last_close = float(candles.iloc[-1]["c"]) if not candles.empty else None
        tick = await client.get_latest_quote(symbol)
        if last_close is not None and tick is not None:
            _, px = tick
            if px > 0:
                diff = abs(px - last_close) / last_close
                if diff >= 0.001:  # >=0.1% резкое движение
                    direction = "вверх" if px > last_close else "вниз"
                    msg = f"⚡ {symbol}: резкое тиковое движение {direction} на {diff*100:.2f}% относительно закрытия последней свечи."
                    events.append(Event(kind="tick_spike", message=msg, importance=2))

        # проверка времени восстановления
        cooldown_sec = cfg.telegram.message_cooldown_minutes * 60
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        for ev in events:
            # Publish signal to Redis (always, regardless of cooldown)
            if integration is not None:
                try:
                    await integration.publish_signal(
                        symbol=symbol,
                        timeframe=timeframe,
                        kind=ev.kind,
                        message=ev.message,
                        importance=ev.importance
                    )
                except Exception as e:
                    logger.warning(f"Failed to publish signal to Redis: {e}")

            last_ts = await cache.get_last_sent(symbol, timeframe, ev.kind)
            time_diff = now_ts - (last_ts or 0)
            cooldown_met = last_ts is None or time_diff >= cooldown_sec
            importance_check = ev.importance >= 2
            should_send = cooldown_met or importance_check

            logger.debug(f"Cooldown check for {symbol} {timeframe} {ev.kind}: last_ts={last_ts}, now_ts={now_ts}, time_diff={time_diff}, cooldown={cooldown_sec}, cooldown_met={cooldown_met}, importance={ev.importance}, importance_check={importance_check}, should_send={should_send}")

            if should_send:
                logger.info(f"Sending message for {symbol} {timeframe} {ev.kind} (cooldown check passed)")
                await notifier.send_message(f"{ev.message} (TF: {timeframe})")
                await cache.set_last_sent(symbol, timeframe, ev.kind, now_ts)
                logger.debug(f"Message sent and cache updated for {symbol} {timeframe} {ev.kind}")
            else:
                logger.info(f"Message skipped for {symbol} {timeframe} {ev.kind} (cooldown not met)")
    except DataProviderException as e:
        logger.error(f"Data provider error for {symbol} {timeframe}: {e}")
        await notifier.send_message(f"⚠️ Ошибка получения данных {symbol} {timeframe}: {e}")
    except AnalysisException as e:
        logger.error(f"Analysis error for {symbol} {timeframe}: {e}")
        await notifier.send_message(f"⚠️ Ошибка анализа {symbol} {timeframe}: {e}")
    except NotificationException as e:
        logger.error(f"Notification error for {symbol} {timeframe}: {e}")
        # Don't send another notification since the notification system itself failed
    except Exception as e:
        logger.error(f"Unexpected error processing {symbol} {timeframe}: {e}")
        await notifier.send_message(f"⚠️ Непредвиденная ошибка обработки {symbol} {timeframe}: {e}")


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
        self.client: Optional[YahooFinanceClient] = None
        self.running = False
        self.paused = False  # For pause/resume commands from Dashboard
        self.integration: Optional[IntegrationManager] = None
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self):
        """Initialize all components"""
        try:
            self.config = load_config(self.config_path)

            self.logger.info(f"Initializing cache with path: {self.config.sqlite_path}")
            self.cache = Cache(self.config.sqlite_path)
            await self.cache.init()

            self.notifier = TelegramNotifier(
                self.config.telegram.bot_token,
                self.config.telegram.chat_id
            )
            self.client = YahooFinanceClient()

            # Initialize Redis integration if enabled
            if self.config.redis.enabled:
                from .integration_manager import IntegrationManager
                self.integration = IntegrationManager(self, self.config.redis)
                await self.integration.start()
                self.logger.info("Redis integration initialized", extra={'event_type': 'redis_init'})

            self.logger.info("Application initialized successfully", extra={'event_type': 'app_init'})
        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}", extra={'event_type': 'init_error'})
            raise
            
    async def cleanup(self):
        """Clean up resources"""
        try:
            # Stop Redis integration first
            if self.integration:
                await self.integration.stop()
                self.logger.info("Redis integration stopped", extra={'event_type': 'redis_cleanup'})

            if self.client:
                await self.client.close()
            if self.notifier:
                await self.notifier.close()
            self.logger.info("Application cleaned up successfully", extra={'event_type': 'app_cleanup'})
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}", extra={'event_type': 'cleanup_error'})

    def pause(self) -> None:
        """Pause agent processing (called from Redis command)."""
        self.paused = True
        self.logger.info("Agent paused via command", extra={'event_type': 'agent_paused'})

    def resume(self) -> None:
        """Resume agent processing (called from Redis command)."""
        self.paused = False
        self.logger.info("Agent resumed via command", extra={'event_type': 'agent_resumed'})
            
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully", extra={'event_type': 'shutdown_signal', 'signal': signum})
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
                        extra={'event_type': 'cycle_complete', 'duration': cycle_duration}
                    )
                except Exception as e:
                    self.logger.error(f"Error in main cycle: {e}", extra={'event_type': 'cycle_error'})
                    
                # Sleep until next poll considering execution time
                interval = min([t.poll_interval_seconds for t in self.config.timeframes]) if self.config.timeframes else 60
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
                extra={'event_type': 'cycle_skipped', 'weekday': weekday, 'hour_gmt': hour}
            )
            return

        tasks: List[asyncio.Task] = []
        errors_count = 0

        for tf_job in self.config.timeframes:
            tf = tf_job.timeframe
            for sym in self.config.pairs:
                tasks.append(asyncio.create_task(process_pair(self.config, self.cache, self.notifier, self.client, sym, tf, self.integration)))
        if self.config.notify_hourly_summary and start_loop.minute == 0:
            tasks.append(asyncio.create_task(hourly_summary(self.config, self.notifier, self.cache)))

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
                active_timeframes=[tf.timeframe for tf in self.config.timeframes]
            )


async def run_agent(args):
    """Legacy function to maintain compatibility"""
    app = Application(args.config)
    await app.initialize()
    await app.run()


async def run_backtest(args):
    """Run backtesting with improved error handling"""
    cfg = load_config(args.config)
    client = YahooFinanceClient()
    
    try:
        # Log the start of backtesting
        logger.info("Starting backtesting", extra={'event_type': 'backtest_start'})
        
        # Run the backtesting cycle across timeframes
        for tf_job in cfg.timeframes:
            tf = tf_job.timeframe
            # Fetch data for each symbol
            for sym in cfg.pairs:
                # Get candles for the specific timeframe and symbol with the specified number of bars
                df = await fetch_candles(client, sym, tf, bars=cfg.backtest.lookback_bars)
                if df.empty:
                    logger.warning(f"No data for {sym} {tf}", extra={'event_type': 'no_data', 'symbol': sym, 'timeframe': tf})
                    continue
                
                # Prepare data for analysis (daily candles)
                daily = daily_from_intraday(df)
                # Analyze the candles
                events = analyze_pair(df, daily, sym, cfg.adx_threshold, cfg.rsi_overbought, cfg.rsi_oversold)
                
                logger.info(f"Backtest {sym} {tf}: {len(events)} events detected", 
                           extra={'event_type': 'backtest_results', 'symbol': sym, 'timeframe': tf, 'event_count': len(events)})
                
                for ev in events:
                    logger.info(f" - {ev.message}", extra={'event_type': 'backtest_event', 'symbol': sym, 'timeframe': tf})
    except Exception as e:
        logger.error(f"Error during backtesting: {e}", extra={'event_type': 'backtest_error'})
        raise
    finally:
        await client.close()
        logger.info("Backtesting completed", extra={'event_type': 'backtest_complete'})


def main():
    """Main entry point with proper error handling"""
    logging.info("Starting Forex Signal Agent...")
    
    parser = argparse.ArgumentParser(description="Forex Signal Agent")
    parser.add_argument("--config", default="config.yaml", help="Путь к YAML конфигу")
    parser.add_argument("--backtest", action="store_true", help="Запустить бэктест и выйти")
    args = parser.parse_args()

    if args.backtest:
        logging.info("Starting Forex Signal Agent in backtest mode...")
        try:
            asyncio.run(run_backtest(args))
        except Exception as e:
            logger.error(f"Backtest error: {e}", extra={'event_type': 'backtest_error'})
            sys.exit(1)
    else:
        logging.info("Starting Forex Signal Agent in normal mode...")
        try:
            asyncio.run(run_agent(args))
        except Exception as e:
            logger.error(f"Agent error: {e}", extra={'event_type': 'agent_error'})
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Agent stopped by user", extra={'event_type': 'agent_shutdown'})
    except Exception as e:
        logger.error(f"Unexpected error: {e}", extra={'event_type': 'unexpected_error'})
        sys.exit(1)
