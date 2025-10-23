from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

import pandas as pd
import pytz

from .config import load_config, AppConfig
from .alpha_vantage_client import AlphaVantageClient, ALPHA_TIMEFRAME_MAP
from .telegram_notifier import TelegramNotifier
from .sqlite_cache import Cache
from .analyzer import analyze_pair, Event


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


async def fetch_candles(client: AlphaVantageClient, symbol: str, timeframe: str, bars: int = 400) -> pd.DataFrame:
    now = int(datetime.now(tz=timezone.utc).timestamp())
    sec = _timeframe_to_seconds(timeframe)
    start = now - sec * (bars + 5)

    resolution = ALPHA_TIMEFRAME_MAP.get(timeframe, timeframe)
    df = await client.get_forex_candles(symbol, resolution, start, now)
    if timeframe == "4h" and resolution == "60min":
        df = AlphaVantageClient.resample_to_4h(df)
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


async def process_pair(cfg: AppConfig, cache: Cache, notifier: TelegramNotifier, client: AlphaVantageClient, symbol: str, timeframe: str):
    try:
        candles = await fetch_candles(client, symbol, timeframe, bars=600)
        if candles.empty:
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

        # cooldown check
        cooldown_sec = cfg.telegram.message_cooldown_minutes * 60
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        for ev in events:
            last_ts = await cache.get_last_sent(symbol, timeframe, ev.kind)
            if last_ts is None or (now_ts - last_ts) >= cooldown_sec or ev.importance >= 2:
                await notifier.send_message(f"{ev.message} (TF: {timeframe}м)")
                await cache.set_last_sent(symbol, timeframe, ev.kind, now_ts)
    except Exception as e:
        await notifier.send_message(f"⚠️ Ошибка обработки {symbol} {timeframe}: {e}")


async def hourly_summary(cfg: AppConfig, notifier: TelegramNotifier, cache: Cache):
    # to avoid duplicates, use meta key
    now = datetime.now(tz=timezone.utc)
    hour_key = now.strftime("%Y-%m-%dT%H")
    already = await cache.get_meta("last_hourly")
    if already == hour_key:
        return
    await notifier.send_message("🕒 Ежечасная проверка агента: всё работает.")
    await cache.set_meta("last_hourly", hour_key)


async def run_agent(args):
    cfg = load_config(args.config)
    tz = pytz.timezone(cfg.timezone)

    cache = Cache(cfg.sqlite_path)
    await cache.init()

    notifier = TelegramNotifier(cfg.telegram.bot_token, cfg.telegram.chat_id)
    client = AlphaVantageClient(cfg.alpha_vantage.api_key, cfg.alpha_vantage.base_url)

    try:
        while True:
            start_loop = datetime.now(tz=timezone.utc)
            tasks: List[asyncio.Task] = []
            for tf_job in cfg.timeframes:
                tf = tf_job.timeframe
                for sym in cfg.pairs:
                    tasks.append(asyncio.create_task(process_pair(cfg, cache, notifier, client, sym, tf)))
            if cfg.notify_hourly_summary and start_loop.minute == 0:
                tasks.append(asyncio.create_task(hourly_summary(cfg, notifier, cache)))
            if tasks:
                await asyncio.gather(*tasks)
            # sleep until next poll according to the smallest poll interval
            interval = min([t.poll_interval_seconds for t in cfg.timeframes]) if cfg.timeframes else 60
            # aim to align to minute boundaries
            elapsed = (datetime.now(tz=timezone.utc) - start_loop).total_seconds()
            sleep_for = max(1, interval - int(elapsed))
            await asyncio.sleep(sleep_for)
    finally:
        await client.close()
        await notifier.close()


async def run_backtest(args):
    cfg = load_config(args.config)
    client = AlphaVantageClient(cfg.alpha_vantage.api_key, cfg.alpha_vantage.base_url)
    try:
        for tf_job in cfg.timeframes:
            tf = tf_job.timeframe
            for sym in cfg.pairs:
                df = await fetch_candles(client, sym, tf, bars=cfg.backtest.lookback_bars)
                if df.empty:
                    print(f"{sym} {tf}: no data")
                    continue
                daily = daily_from_intraday(df)
                events = analyze_pair(df, daily, sym, cfg.adx_threshold, cfg.rsi_overbought, cfg.rsi_oversold)
                print(f"Backtest {sym} {tf}: последние события: ")
                for ev in events:
                    print(" -", ev.message)
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="Forex Signal Agent")
    parser.add_argument("--config", default="config.yaml", help="Путь к YAML конфигу")
    parser.add_argument("--backtest", action="store_true", help="Запустить бэктест и выйти")
    args = parser.parse_args()

    if args.backtest:
        asyncio.run(run_backtest(args))
    else:
        asyncio.run(run_agent(args))
