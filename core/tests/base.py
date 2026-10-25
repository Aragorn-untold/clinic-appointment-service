from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import Appointment
from doctor_slots.models import DoctorSlot
from doctors.models import Doctor
from specializations.models import Specialization

PASSWORD = "test-password-123"


class BaseTestCase(TestCase):
    """Shared test data for all apps. Inherit from it instead of building
    users, doctors and slots in every test file.

    Data from setUpTestData is created once per class and rolled back after it.
    Clients are created in setUp so each test gets fresh ones.
    """

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            email="patient@example.com",
            password=PASSWORD,
            first_name="Ivan",
            last_name="Petrenko",
        )
        cls.admin_user = user_model.objects.create_superuser(
            email="admin@example.com",
            password=PASSWORD,
        )
        cls.specialization = Specialization.objects.create(
            name="Cardiology",
            code="cardiology",
        )
        cls.doctor = Doctor.objects.create(
            first_name="Olena",
            last_name="Kovalenko",
            price_per_visit=Decimal("800.00"),
        )
        cls.doctor.specializations.add(cls.specialization)

        now = timezone.now().replace(second=0, microsecond=0)
        start = now + timedelta(days=1)
        cls.slot = DoctorSlot.objects.create(
            doctor=cls.doctor,
            start=start,
            end=start + timedelta(minutes=30),
        )
        cls.appointment = Appointment.objects.create(
            doctor_slot=cls.slot,
            patient=cls.user,
            price=cls.doctor.price_per_visit,
        )

    def setUp(self):
        # Redis is not rolled back with the test database, so cached lists
        # and throttle counters would leak between tests and test runs.
        cache.clear()

        self.client = APIClient()

        self.auth_client = APIClient()
        self.auth_client.force_authenticate(user=self.user)

        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin_user)
