from __future__ import annotations

import aiosqlite
from typing import Optional
from datetime import datetime, timezone


class Cache:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self):
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

    async def get_last_sent(self, symbol: str, timeframe: str, kind: str) -> Optional[int]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT last_sent_ts FROM events WHERE symbol=? AND timeframe=? AND kind=?", (symbol, timeframe, kind)) as cur:
                row = await cur.fetchone()
                return int(row["last_sent_ts"]) if row else None

    async def set_last_sent(self, symbol: str, timeframe: str, kind: str, ts: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO events(symbol, timeframe, kind, last_sent_ts) VALUES(?,?,?,?)\n                 ON CONFLICT(symbol, timeframe, kind) DO UPDATE SET last_sent_ts=excluded.last_sent_ts",
                (symbol, timeframe, kind, ts),
            )
            await db.commit()

    async def get_meta(self, key: str) -> Optional[str]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT value FROM meta WHERE key=?", (key,)) as cur:
                row = await cur.fetchone()
                return row["value"] if row else None

    async def set_meta(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO meta(key, value) VALUES(?,?)\n                 ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            await db.commit()
