import requests
from django.conf import settings


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text},
        timeout=10,
    )
    response.raise_for_status()
