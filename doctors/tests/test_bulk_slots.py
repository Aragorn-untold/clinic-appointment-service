# doctors/tests/test_bulk_slots.py
from datetime import datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from core.tests.base import BaseTestCase
from doctor_slots.models import DoctorSlot


def bulk_slots_url(doctor_id):
    return reverse("doctors:doctor-slots", args=[doctor_id])


class BulkSlotCreateTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # A week ahead: far from BaseTestCase's slot (tomorrow) and never in the past
        cls.workday = timezone.localdate() + timedelta(days=7)

    def aware(self, hour, minute=0):
        return timezone.make_aware(datetime.combine(self.workday, time(hour, minute)))

    def payload(self, **overrides):
        data = {
            "date": self.workday.isoformat(),
            "start_time": "09:00",
            "end_time": "17:00",
            "slot_length_minutes": 30,
        }
        data.update(overrides)
        return data

    def doctor_slots_on_workday(self):
        return DoctorSlot.objects.filter(doctor=self.doctor, start__date=self.workday)

    # --- happy path ---

    def test_admin_creates_slots_for_whole_day(self):
        res = self.admin_client.post(bulk_slots_url(self.doctor.id), self.payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data), 16)
        self.assertEqual(self.doctor_slots_on_workday().count(), 16)

        first = DoctorSlot.objects.get(pk=res.data[0]["id"])
        self.assertEqual(first.start, self.aware(9, 0))
        self.assertEqual(first.end, self.aware(9, 30))
        self.assertEqual(res.data[0]["doctor"], self.doctor.id)

    def test_remainder_shorter_than_slot_is_dropped(self):
        res = self.admin_client.post(
            bulk_slots_url(self.doctor.id),
            self.payload(end_time="10:45"),
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data), 3)
        self.assertEqual(
            self.doctor_slots_on_workday().order_by("end").last().end,
            self.aware(10, 30),
        )

    # --- overlaps ---

    def test_slot_matching_existing_one_is_skipped(self):
        DoctorSlot.objects.create(doctor=self.doctor, start=self.aware(10, 0), end=self.aware(10, 30))

        res = self.admin_client.post(bulk_slots_url(self.doctor.id), self.payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data), 15)
        self.assertEqual(
            self.doctor_slots_on_workday().filter(start=self.aware(10, 0)).count(),
            1,
        )

    def test_partially_overlapping_slots_are_skipped(self):
        # 10:15-10:45 overlaps both 10:00-10:30 and 10:30-11:00
        DoctorSlot.objects.create(doctor=self.doctor, start=self.aware(10, 15), end=self.aware(10, 45))

        res = self.admin_client.post(bulk_slots_url(self.doctor.id), self.payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        created_starts = {DoctorSlot.objects.get(pk=item["id"]).start for item in res.data}
        self.assertEqual(len(created_starts), 14)
        self.assertNotIn(self.aware(10, 0), created_starts)
        self.assertNotIn(self.aware(10, 30), created_starts)

    def test_adjacent_existing_slot_does_not_block(self):
        # Ends exactly when the generated day starts: touching is not overlapping
        DoctorSlot.objects.create(doctor=self.doctor, start=self.aware(8, 30), end=self.aware(9, 0))

        res = self.admin_client.post(bulk_slots_url(self.doctor.id), self.payload(), format="json")

        self.assertEqual(len(res.data), 16)

    def test_repeated_request_creates_nothing(self):
        url = bulk_slots_url(self.doctor.id)
        self.admin_client.post(url, self.payload(), format="json")

        res = self.admin_client.post(url, self.payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data, [])
        self.assertEqual(self.doctor_slots_on_workday().count(), 16)

    def test_slot_longer_than_working_period_creates_nothing(self):
        res = self.admin_client.post(
            bulk_slots_url(self.doctor.id),
            self.payload(start_time="09:00", end_time="09:20"),
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data, [])

    # --- validation ---

    def test_end_before_start_returns_400(self):
        res = self.admin_client.post(
            bulk_slots_url(self.doctor.id),
            self.payload(start_time="17:00", end_time="09:00"),
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", res.data)
        self.assertFalse(self.doctor_slots_on_workday().exists())

    def test_past_date_returns_400(self):
        yesterday = timezone.localdate() - timedelta(days=1)

        res = self.admin_client.post(
            bulk_slots_url(self.doctor.id),
            self.payload(date=yesterday.isoformat()),
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date", res.data)

    def test_slot_length_out_of_range_returns_400(self):
        for minutes in (0, 4, 241):
            with self.subTest(minutes=minutes):
                res = self.admin_client.post(
                    bulk_slots_url(self.doctor.id),
                    self.payload(slot_length_minutes=minutes),
                    format="json",
                )

                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("slot_length_minutes", res.data)

    # --- permissions / lookup ---

    def test_anonymous_cannot_create_slots(self):
        res = self.client.post(bulk_slots_url(self.doctor.id), self.payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_create_slots(self):
        res = self.auth_client.post(bulk_slots_url(self.doctor.id), self.payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.doctor_slots_on_workday().exists())

    def test_unknown_doctor_returns_404(self):
        res = self.admin_client.post(bulk_slots_url(999999), self.payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
