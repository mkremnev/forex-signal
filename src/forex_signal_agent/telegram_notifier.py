from __future__ import annotations
from typing import Optional

import httpx
import logging
from httpx import HTTPStatusError, HTTPError

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=20.0)

    async def close(self):
        await self._client.aclose()

    async def send_message(self, text: str, parse_mode: Optional[str] = None, disable_web_page_preview: bool = True) -> None:
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
            
        try:
            logger.info(f"""Sending message to Telegram... - /n{payload}""")
            r = await self._client.post(url, json=payload)
            r.raise_for_status()
        except HTTPStatusError as e:
            # Обработка HTTP-ошибок (например, 400, 500 и т.д.)
            print('error', e)
            logger.error(f"Network error while sending message to Telegram: {e}")
        except HTTPError as e:
            print('error', e)
            logger.error(f"Network error while sending message to Telegram: {e}")
