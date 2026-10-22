from datetime import date, datetime, time

from django.test import SimpleTestCase

from doctors.services import generate_slots


class GenerateSlotsTests(SimpleTestCase):
    def setUp(self):
        self.workday = date(2026, 10, 22)

    def test_generates_consecutive_slots(self):
        slots = generate_slots(self.workday, time(9, 0), time(11, 0), 30)

        self.assertEqual(
            slots,
            [
                (datetime(2026, 10, 22, 9, 0), datetime(2026, 10, 22, 9, 30)),
                (datetime(2026, 10, 22, 9, 30), datetime(2026, 10, 22, 10, 0)),
                (datetime(2026, 10, 22, 10, 0), datetime(2026, 10, 22, 10, 30)),
                (datetime(2026, 10, 22, 10, 30), datetime(2026, 10, 22, 11, 0)),
            ],
        )

    def test_slots_do_not_overlap_and_have_equal_length(self):
        slots = generate_slots(self.workday, time(8, 0), time(17, 0), 20)

        for start, end in slots:
            self.assertEqual((end - start).total_seconds(), 20 * 60)
        for (_, prev_end), (next_start, _) in zip(slots, slots[1:]):
            self.assertEqual(prev_end, next_start)

    def test_slots_are_on_given_date(self):
        slots = generate_slots(self.workday, time(9, 0), time(10, 0), 15)

        for start, end in slots:
            self.assertEqual(start.date(), self.workday)
            self.assertEqual(end.date(), self.workday)

    def test_incomplete_last_slot_is_dropped(self):
        slots = generate_slots(self.workday, time(9, 0), time(10, 0), 25)

        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[-1][1], datetime(2026, 10, 22, 9, 50))

    def test_single_slot_when_slot_equals_workday(self):
        slots = generate_slots(self.workday, time(9, 0), time(10, 0), 60)

        self.assertEqual(
            slots,
            [(datetime(2026, 10, 22, 9, 0), datetime(2026, 10, 22, 10, 0))],
        )

    def test_return_naive_datetime(self):
        slots = generate_slots(self.workday, time(9, 0), time(11, 30), 30)

        for start, end in slots:
            self.assertIsNone(start.tzinfo)
            self.assertIsNone(end.tzinfo)

    def test_start_equal_to_end_raises(self):
        with self.assertRaisesMessage(
            ValueError, "start_time must be earlier than end_time"
        ):
            generate_slots(self.workday, time(9, 0), time(9, 0), 30)

    def test_start_after_end_raises(self):
        with self.assertRaisesMessage(
            ValueError, "start_time must be earlier than end_time"
        ):
            generate_slots(self.workday, time(18, 0), time(9, 0), 30)

    def test_zero_slot_length_raises(self):
        with self.assertRaisesMessage(
            ValueError, "slot_length_minutes must be positive, got 0"
        ):
            generate_slots(self.workday, time(9, 0), time(17, 0), 0)

    def test_negative_slot_length_raises(self):
        with self.assertRaisesMessage(
            ValueError, "slot_length_minutes must be positive, got -15"
        ):
            generate_slots(self.workday, time(9, 0), time(17, 0), -15)

    def test_slot_longer_than_workday_returns_empty_list(self):
        slots = generate_slots(self.workday, time(9, 0), time(9, 30), 45)

        self.assertEqual(slots, [])
