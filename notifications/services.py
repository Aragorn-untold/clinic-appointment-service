# Functions for sending notifications
import logging

logger = logging.getLogger(__name__)


def notify_admins(text: str) -> None:
    """Ставит Celery-задачу отправки сообщения в Telegram-чат админов.
    Заглушка: пишет в лог."""
    # TODO: replace with telegram once Celery + Telegram are wired up
    logger.info("Admin notification (stub): %s", text)
