from unittest.mock import patch

from django.db import transaction
from django.test import TestCase
from kombu.exceptions import OperationalError

from notifications.services import notify_admins

DELAY = "notifications.services.send_telegram_message_task.delay"


class NotifyAdminsTests(TestCase):
    """notify_admins queues the message after commit and never raises."""

    @patch(DELAY)
    def test_message_is_queued_only_after_commit(self, mock_delay):
        with self.captureOnCommitCallbacks() as callbacks:
            notify_admins("hello")
            mock_delay.assert_not_called()

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        mock_delay.assert_called_once_with("hello")

    @patch(DELAY)
    def test_nothing_is_sent_when_transaction_rolls_back(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    notify_admins("this change was rolled back")
                    raise RuntimeError("rollback")
            except RuntimeError:
                pass

        mock_delay.assert_not_called()

    @patch(DELAY, side_effect=OperationalError("Redis is down"))
    def test_does_not_raise_when_redis_is_down(self, mock_delay):
        with (
            self.assertLogs("notifications.services", level="ERROR") as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            notify_admins("hello")

        mock_delay.assert_called_once_with("hello")
        self.assertIn("Could not queue admin notification", logs.output[0])

    @patch(DELAY, side_effect=Exception("anything else"))
    def test_does_not_raise_on_any_error(self, mock_delay):
        with self.assertLogs("notifications.services", level="ERROR"), self.captureOnCommitCallbacks(execute=True):
            notify_admins("hello")
