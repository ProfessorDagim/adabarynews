from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class PublishedMessage:
    message_id: int


class TelegramPublisher:
    """Minimal Telegram Bot API client for approval-based text publishing."""

    def __init__(self, bot_token: str) -> None:
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.endpoint = f"{self.api_url}/sendMessage"

    async def publish(
        self, channel_id: str, text: str, client: httpx.AsyncClient | None = None
    ) -> PublishedMessage:
        owns_client = client is None
        client = client or httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.post(
                self.endpoint,
                json={
                    "chat_id": channel_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result") if payload.get("ok") else None
            message_id = result.get("message_id") if isinstance(result, dict) else None
            if not isinstance(message_id, int):
                description = payload.get("description", "Telegram did not return a message ID")
                raise ValueError(str(description))
            return PublishedMessage(message_id=message_id)
        finally:
            if owns_client:
                await client.aclose()

    async def send_message(
        self, chat_id: str, text: str, reply_markup: dict[str, object] | None = None
    ) -> PublishedMessage:
        payload: dict[str, object] = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.endpoint, json=payload)
            response.raise_for_status()
        result = response.json().get("result")
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise ValueError("Telegram did not return a message ID")
        return PublishedMessage(message_id=result["message_id"])

    async def answer_callback(self, callback_id: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_url}/answerCallbackQuery", json={"callback_query_id": callback_id, "text": text}
            )
            response.raise_for_status()

    async def set_webhook(self, url: str, secret_token: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_url}/setWebhook",
                json={"url": url, "secret_token": secret_token, "allowed_updates": ["message", "callback_query"]},
            )
            response.raise_for_status()
