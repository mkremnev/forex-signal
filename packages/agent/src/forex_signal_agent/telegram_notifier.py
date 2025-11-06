from __future__ import annotations
from typing import Optional

import httpx
import logging
from httpx import HTTPStatusError, HTTPError

from .exceptions import NotificationException

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        # Create a masked token for safe logging
        self._masked_token = self._mask_token(bot_token) if bot_token else "****"
        self._client = httpx.AsyncClient(timeout=20.0)

    def _mask_token(self, token: str) -> str:
        """Mask the bot token for safe logging"""
        if len(token) > 10:
            return f"{token[:5]}...{token[-3:]}"
        return "****"

    async def close(self):
        await self._client.aclose()

    async def send_message(self, text: str, parse_mode: Optional[str] = None, disable_web_page_preview: bool = True) -> None:
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram token or chat_id not configured, skipping message", extra={'event_type': 'notification_skipped'})
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
            logger.info(
                f"Sending message to Telegram (chat_id: {self.chat_id})",
                extra={'event_type': 'notification_attempt', 'chat_id': self.chat_id}
            )
            r = await self._client.post(url, json=payload)
            r.raise_for_status()
            logger.info(
                f"Message sent successfully to Telegram (chat_id: {self.chat_id})",
                extra={'event_type': 'notification_success', 'chat_id': self.chat_id}
            )
        except HTTPStatusError as e:
            logger.error(
                f"HTTP error while sending message to Telegram (chat_id: {self.chat_id}, status: {e.response.status_code})",
                extra={'event_type': 'notification_http_error', 'chat_id': self.chat_id, 'status_code': e.response.status_code}
            )
            raise NotificationException(f"HTTP error while sending message: {e}")
        except HTTPError as e:
            logger.error(
                f"Network error while sending message to Telegram (chat_id: {self.chat_id})",
                extra={'event_type': 'notification_network_error', 'chat_id': self.chat_id}
            )
            raise NotificationException(f"Network error while sending message: {e}")
