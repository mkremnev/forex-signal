from __future__ import annotations

import aiosqlite
import logging
from typing import Optional


logger = logging.getLogger(__name__)


class Cache:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self):
        logger.info(f"Initializing cache database at: {self.path}")
        try:
            async with aiosqlite.connect(self.path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        last_sent_ts INTEGER NOT NULL
                    )
                    """
                )
                await db.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_events_unique
                    ON events(symbol, timeframe, kind)
                    """
                )
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS meta (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                    """
                )
                await db.commit()
                logger.info("Cache database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cache database: {e}")
            raise

    async def get_last_sent(self, symbol: str, timeframe: str, kind: str) -> Optional[int]:
        try:
            async with aiosqlite.connect(self.path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT last_sent_ts FROM events WHERE symbol=? AND timeframe=? AND kind=?", (symbol, timeframe, kind)) as cur:
                    row = await cur.fetchone()
                    result = int(row["last_sent_ts"]) if row else None
                    logger.debug(f"Cache get_last_sent: symbol={symbol}, timeframe={timeframe}, kind={kind}, result={result}")
                    return result
        except Exception as e:
            logger.error(f"Cache get_last_sent failed for {symbol}, {timeframe}, {kind}: {e}")
            return None

    async def set_last_sent(self, symbol: str, timeframe: str, kind: str, ts: int) -> None:
        logger.debug(f"Cache set_last_sent: symbol={symbol}, timeframe={timeframe}, kind={kind}, ts={ts}")
        try:
            async with aiosqlite.connect(self.path) as db:
                cursor = await db.execute(
                    """INSERT INTO events(symbol, timeframe, kind, last_sent_ts) 
                       VALUES(?,?,?,?) 
                       ON CONFLICT(symbol, timeframe, kind) 
                       DO UPDATE SET last_sent_ts=excluded.last_sent_ts""",
                    (symbol, timeframe, kind, ts)
                )
                await db.commit()
                logger.debug(f"Cache set_last_sent successful for {symbol}, {timeframe}, {kind}, ts={ts}")
        except Exception as e:
            logger.error(f"Cache set_last_sent failed for {symbol}, {timeframe}, {kind}, ts={ts}: {e}")
            raise

    async def get_meta(self, key: str) -> Optional[str]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT value FROM meta WHERE key=?", (key,)) as cur:
                row = await cur.fetchone()
                result = row["value"] if row else None
                logger.debug(f"Cache get_meta: key={key}, result={result}")
                return result

    async def set_meta(self, key: str, value: str) -> None:
        logger.debug(f"Cache set_meta: key={key}, value={value}")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO meta(key, value) VALUES(?,?)\n                 ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            await db.commit()
