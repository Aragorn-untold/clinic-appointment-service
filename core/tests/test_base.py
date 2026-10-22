from decimal import Decimal

from appointments.models import Appointment
from core.tests.base import BaseTestCase


class BaseTestCaseTests(BaseTestCase):
    def test_shared_data_is_created(self):
        self.assertFalse(self.user.is_staff)
        self.assertTrue(self.admin_user.is_staff)
        self.assertIn(self.specialization, self.doctor.specializations.all())
        self.assertEqual(self.slot.doctor, self.doctor)
        self.assertEqual(self.appointment.doctor_slot, self.slot)
        self.assertEqual(self.appointment.patient, self.user)

    def test_appointment_is_booked_with_doctor_price(self):
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)
        self.assertEqual(self.appointment.price, Decimal("800.00"))

    def test_clients_are_authenticated_as_expected_users(self):
        self.assertEqual(self.auth_client.handler._force_user, self.user)
        self.assertEqual(
            self.admin_client.handler._force_user, self.admin_user
        )
        self.assertIsNone(self.client.handler._force_user)
