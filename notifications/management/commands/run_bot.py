import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Telegram bot that replies to /start with the chat_id.

    Use it once to find the value for TELEGRAM_CHAT_ID. Runs as the `bot`
    service in docker-compose, which is off by default:

        docker compose --profile bot up bot

    Telegram allows only one process to poll a bot token at a time. If the
    bot already runs somewhere else, this one logs "409 Conflict" and retries.
    """

    help = "Run the Telegram bot that replies to /start with the chat_id."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError("There is no Telegram bot token in settings")
        bot_api = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
        offset = None
        self.stdout.write("Bot started")
        while True:
            try:
                resp = requests.get(
                    f"{bot_api}/getUpdates",
                    params={"timeout": 30, "offset": offset},
                    timeout=35,
                )
                resp.raise_for_status()
                for update in resp.json().get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message")
                    if message and message.get("text", "").startswith("/start"):
                        chat_id = message["chat"]["id"]
                        text = f"chat_id: {chat_id}"
                        requests.post(
                            f"{bot_api}/sendMessage",
                            json={"chat_id": chat_id, "text": text},
                            timeout=10,
                        )
            except requests.RequestException as exc:
                status = getattr(exc.response, "status_code", "")
                self.stderr.write(f"Telegram unavailable: {exc.__class__.__name__} {status}".strip())
                time.sleep(5)
