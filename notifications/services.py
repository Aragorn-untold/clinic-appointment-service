import logging

from django.db import transaction

from notifications.tasks import send_telegram_message_task

logger = logging.getLogger(__name__)


def notify_admins(text: str) -> None:
    """Queue a Telegram message for admins once the current transaction commits.

    Never raises: a broken notification (e.g. Redis is down) must not fail
    or roll back the action it reports on.
    """
    transaction.on_commit(lambda: queue_message(text))


def queue_message(text: str) -> None:
    try:
        send_telegram_message_task.delay(text)
    except Exception:
        logger.exception("Could not queue admin notification: %s", text)
