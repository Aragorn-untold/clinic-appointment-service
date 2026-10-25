from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.management.commands import seed_demo
from doctor_slots.models import DoctorSlot
from doctors.models import Doctor
from specializations.models import Specialization

SLOTS_PER_DAY = 8  # 09:00-13:00 by 30 minutes
EXPECTED_SLOTS = len(seed_demo.DOCTORS) * seed_demo.SLOT_DAYS * SLOTS_PER_DAY


# The specialization signal clears the Redis cache; the command logic doesn't depend on it
@patch("specializations.signals.cache")
class SeedDemoCommandTests(TestCase):
    def run_command(self):
        out = StringIO()
        call_command("seed_demo", stdout=out)
        return out.getvalue()

    def test_creates_all_demo_data(self, _cache):
        output = self.run_command()

        self.assertEqual(Specialization.objects.count(), len(seed_demo.SPECIALIZATIONS))
        self.assertEqual(Doctor.objects.count(), len(seed_demo.DOCTORS))
        self.assertEqual(get_user_model().objects.count(), len(seed_demo.DEMO_USERS))
        self.assertEqual(DoctorSlot.objects.count(), EXPECTED_SLOTS)
        self.assertIn("Demo data is ready.", output)

    def test_running_twice_does_not_duplicate_anything(self, _cache):
        self.run_command()
        counts = (
            Specialization.objects.count(),
            Doctor.objects.count(),
            get_user_model().objects.count(),
            DoctorSlot.objects.count(),
        )

        output = self.run_command()

        self.assertEqual(
            counts,
            (
                Specialization.objects.count(),
                Doctor.objects.count(),
                get_user_model().objects.count(),
                DoctorSlot.objects.count(),
            ),
        )
        self.assertIn("Slots created: 0", output)

    def test_doctor_gets_all_listed_specializations(self, _cache):
        self.run_command()

        for data in seed_demo.DOCTORS:
            with self.subTest(doctor=data["last_name"]):
                doctor = Doctor.objects.get(first_name=data["first_name"], last_name=data["last_name"])
                self.assertEqual(
                    set(doctor.specializations.values_list("code", flat=True)),
                    set(data["specializations"]),
                )

    def test_demo_users_can_log_in_with_demo_password(self, _cache):
        self.run_command()
        user_model = get_user_model()

        for data in seed_demo.DEMO_USERS:
            with self.subTest(email=data["email"]):
                user = user_model.objects.get(email=data["email"])
                self.assertTrue(user.check_password(seed_demo.DEMO_PASSWORD))
                self.assertEqual(user.is_staff, data["is_admin"])

    def test_slots_are_upcoming_weekdays_only(self, _cache):
        self.run_command()
        today = timezone.localdate()

        for slot in DoctorSlot.objects.all():
            local_start = timezone.localtime(slot.start)
            self.assertGreater(local_start.date(), today)
            self.assertLess(local_start.weekday(), 5)
            self.assertEqual(slot.end - slot.start, timedelta(minutes=30))

    def test_existing_records_are_kept_unchanged(self, _cache):
        Specialization.objects.create(code="cardiology", name="Heart stuff")
        doctor = Doctor.objects.create(first_name="Olena", last_name="Kovalenko", price_per_visit="999.00")

        self.run_command()

        self.assertEqual(Specialization.objects.get(code="cardiology").name, "Heart stuff")
        doctor.refresh_from_db()
        self.assertEqual(str(doctor.price_per_visit), "999.00")
        self.assertEqual(Doctor.objects.filter(last_name="Kovalenko").count(), 1)

    def test_existing_slot_is_not_overlapped(self, _cache):
        self.run_command()
        first_slot = DoctorSlot.objects.order_by("start", "doctor_id").first()
        doctor, start = first_slot.doctor, first_slot.start
        hour_later = start + timedelta(hours=1)
        # Free 09:00-10:00 (two 30-minute slots) and put one 1-hour slot there
        DoctorSlot.objects.filter(doctor=doctor, start__gte=start, end__lte=hour_later).delete()
        DoctorSlot.objects.create(doctor=doctor, start=start, end=hour_later)

        output = self.run_command()

        self.assertIn("Slots created: 0", output)
        overlapping = DoctorSlot.objects.filter(doctor=doctor, start__lt=hour_later, end__gt=start)
        self.assertEqual(overlapping.count(), 1)
