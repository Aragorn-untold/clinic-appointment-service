from celery import shared_task
from requests import RequestException

from notifications.telegram import send_telegram_message


@shared_task(autoretry_for=(RequestException,), retry_backoff=True, max_retries=5)
def send_telegram_message_task(text: str) -> None:
    send_telegram_message(text)
