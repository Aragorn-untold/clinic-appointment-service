from io import StringIO
from unittest.mock import MagicMock, patch

import requests
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

BOT_API = "https://api.telegram.org/bottest-token"


class StopBot(Exception):
    """Raised by a mock to break the bot's endless loop."""


def updates_response(*updates):
    response = MagicMock()
    response.json.return_value = {"ok": True, "result": list(updates)}
    return response


def message_update(update_id, text, chat_id=111):
    return {
        "update_id": update_id,
        "message": {"chat": {"id": chat_id}, "text": text},
    }


@override_settings(TELEGRAM_BOT_TOKEN="test-token")
@patch("notifications.management.commands.run_bot.time.sleep")
@patch("notifications.management.commands.run_bot.requests.post")
@patch("notifications.management.commands.run_bot.requests.get")
class RunBotCommandTests(SimpleTestCase):
    def run_bot(self, get_mock, *get_results):
        """Run the loop once per result, then stop it."""
        get_mock.side_effect = [*get_results, StopBot()]
        self.stdout = StringIO()
        self.stderr = StringIO()

        with self.assertRaises(StopBot):
            call_command("run_bot", stdout=self.stdout, stderr=self.stderr)

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_missing_token_stops_before_polling(self, get_mock, post_mock, sleep_mock):
        with self.assertRaisesMessage(ValueError, "There is no Telegram bot token in settings"):
            call_command("run_bot", stdout=StringIO())

        get_mock.assert_not_called()

    def test_prints_start_message(self, get_mock, post_mock, sleep_mock):
        self.run_bot(get_mock)

        self.assertIn("Bot started", self.stdout.getvalue())

    def test_polls_get_updates_with_long_polling(self, get_mock, post_mock, sleep_mock):
        self.run_bot(get_mock)

        get_mock.assert_called_once_with(
            f"{BOT_API}/getUpdates",
            params={"timeout": 30, "offset": None},
            timeout=35,
        )

    def test_start_replies_with_chat_id(self, get_mock, post_mock, sleep_mock):
        self.run_bot(get_mock, updates_response(message_update(1, "/start", chat_id=-100500)))

        post_mock.assert_called_once_with(
            f"{BOT_API}/sendMessage",
            json={"chat_id": -100500, "text": "chat_id: -100500"},
            timeout=10,
        )

    def test_start_with_bot_name_in_group_replies(self, get_mock, post_mock, sleep_mock):
        self.run_bot(get_mock, updates_response(message_update(1, "/start@ClinicBot")))

        post_mock.assert_called_once()
        self.assertEqual(post_mock.call_args.kwargs["json"]["chat_id"], 111)

    def test_ignores_updates_without_start_command(self, get_mock, post_mock, sleep_mock):
        updates = (
            message_update(1, "hello"),
            {"update_id": 2, "message": {"chat": {"id": 111}}},  # e.g. a photo, no text
            {"update_id": 3, "edited_message": {"chat": {"id": 111}, "text": "/start"}},
        )

        self.run_bot(get_mock, updates_response(*updates))

        post_mock.assert_not_called()

    def test_replies_to_each_start_in_one_batch(self, get_mock, post_mock, sleep_mock):
        updates = (
            message_update(1, "/start", chat_id=1),
            message_update(2, "/start", chat_id=2),
        )

        self.run_bot(get_mock, updates_response(*updates))

        chat_ids = [call.kwargs["json"]["chat_id"] for call in post_mock.call_args_list]
        self.assertEqual(chat_ids, [1, 2])

    def test_offset_moves_past_last_update(self, get_mock, post_mock, sleep_mock):
        self.run_bot(
            get_mock,
            updates_response(message_update(41, "hi"), message_update(42, "hi")),
            updates_response(),
        )

        offsets = [call.kwargs["params"]["offset"] for call in get_mock.call_args_list]
        self.assertEqual(offsets, [None, 43, 43])

    def test_network_error_is_logged_and_bot_keeps_running(self, get_mock, post_mock, sleep_mock):
        self.run_bot(
            get_mock,
            requests.ConnectionError("no network"),
            updates_response(message_update(1, "/start")),
        )

        self.assertIn("Telegram unavailable: ConnectionError", self.stderr.getvalue())
        sleep_mock.assert_called_once_with(5)
        post_mock.assert_called_once()

    def test_http_error_is_logged_and_bot_keeps_running(self, get_mock, post_mock, sleep_mock):
        conflict = MagicMock()
        conflict.raise_for_status.side_effect = requests.HTTPError("409 Conflict")

        self.run_bot(get_mock, conflict, updates_response(message_update(1, "/start")))

        self.assertIn("Telegram unavailable: HTTPError", self.stderr.getvalue())
        sleep_mock.assert_called_once_with(5)
        post_mock.assert_called_once()

    def test_send_error_is_logged_and_bot_keeps_running(self, get_mock, post_mock, sleep_mock):
        post_mock.side_effect = requests.Timeout()

        self.run_bot(get_mock, updates_response(message_update(1, "/start")))

        self.assertIn("Telegram unavailable: Timeout", self.stderr.getvalue())
        sleep_mock.assert_called_once_with(5)
