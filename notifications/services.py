from notifications.tasks import send_telegram_message_task


def notify_admins(text: str) -> None:
    send_telegram_message_task.delay(text)
