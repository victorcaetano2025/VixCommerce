import unittest
from unittest.mock import call, patch

from services.orders import outbox_publisher


class OutboxPublisherTests(unittest.TestCase):
    def test_marks_event_published_after_successful_publish(self):
        event = {"id": "event-1"}

        with (
            patch.object(outbox_publisher, "get_pending_events", return_value=[event]),
            patch.object(outbox_publisher, "publish_event") as publish,
            patch.object(outbox_publisher, "mark_event_as_published") as mark,
        ):
            outbox_publisher.process_outbox()

        publish.assert_called_once_with(event)
        mark.assert_called_once_with("event-1")

    def test_keeps_event_pending_when_publish_fails(self):
        event = {"id": "event-1"}

        with (
            patch.object(outbox_publisher, "get_pending_events", return_value=[event]),
            patch.object(
                outbox_publisher,
                "publish_event",
                side_effect=OSError("broker unavailable"),
            ),
            patch.object(outbox_publisher, "mark_event_as_published") as mark,
        ):
            outbox_publisher.process_outbox()

        mark.assert_not_called()

    @patch.object(
        outbox_publisher.time,
        "sleep",
        side_effect=[None, KeyboardInterrupt],
    )
    @patch.object(outbox_publisher, "process_outbox")
    def test_run_publisher_processes_each_poll(
        self,
        process_outbox,
        sleep,
    ):
        with self.assertRaises(KeyboardInterrupt):
            outbox_publisher.run_publisher()

        self.assertEqual(process_outbox.call_count, 2)
        self.assertEqual(
            sleep.call_args_list,
            [
                call(outbox_publisher.POLL_INTERVAL_SECONDS),
                call(outbox_publisher.POLL_INTERVAL_SECONDS),
            ],
        )


if __name__ == "__main__":
    unittest.main()
