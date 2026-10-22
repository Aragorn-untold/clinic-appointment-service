from decimal import Decimal

from core.tests.base import BaseTestCase
from specializations.models import Specialization


class DoctorTests(BaseTestCase):
    def test_str_returns_full_name(self):
        self.assertEqual(str(self.doctor), "Olena Kovalenko")

    def test_price_is_decimal(self):
        self.doctor.refresh_from_db()
        self.assertIsInstance(self.doctor.price_per_visit, Decimal)
        self.assertEqual(self.doctor.price_per_visit, Decimal("800.00"))

    def test_doctor_can_have_many_specializations(self):
        therapy = Specialization.objects.create(name="Therapy", code="therapy")
        self.doctor.specializations.add(therapy)

        self.assertEqual(self.doctor.specializations.count(), 2)
        self.assertIn(self.doctor, therapy.doctors.all())
