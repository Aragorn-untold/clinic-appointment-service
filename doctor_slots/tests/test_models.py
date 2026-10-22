from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from doctor_slots.models import DoctorSlot
from doctors.models import Doctor


class DoctorSlotTests(TestCase):
    def setUp(self):
        self.doctor = Doctor.objects.create(
            first_name="Olena",
            last_name="Kovalenko",
            price_per_visit=800,
        )
        self.start = timezone.now() + timedelta(days=1)

        DoctorSlot.objects.create(
            doctor=self.doctor,
            start=self.start,
            end=self.start + timedelta(minutes=30),
        )

    def test_overlapping_slot_is_rejected(self):
        with self.assertRaises(ValueError):
            DoctorSlot.objects.create(
                doctor=self.doctor,
                start=self.start + timedelta(minutes=15),
                end=self.start + timedelta(minutes=45),
            )
