import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    For task 6.3 only, do not use this bcz the bot already listens to chat.
    This command is here to satisfy 12.a requirement from:
    https://docs.google.com/document/d/1vBLGUwsyM212ReQofTeCEjgNIj4H9myX/edit
    DO NOT USE IT
    won't work anyway
    """

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
