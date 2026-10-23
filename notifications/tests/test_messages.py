from decimal import Decimal

from django.utils import timezone

from core.tests.base import BaseTestCase
from notifications import messages
from payments.models import Payment


class AppointmentMessagesTests(BaseTestCase):
    def assert_has_appointment_details(self, text):
        start = timezone.localtime(self.slot.start).strftime(messages.TIME_FORMAT)
        self.assertIn("Patient: Ivan Petrenko (patient@example.com)", text)
        self.assertIn("Doctor: Olena Kovalenko", text)
        self.assertIn(f"Time: {start}", text)
        self.assertIn("Price: 800.00", text)

    def test_each_message_has_title_and_appointment_details(self):
        cases = (
            (messages.appointment_booked, "New appointment"),
            (messages.appointment_cancelled, "Appointment cancelled"),
            (messages.appointment_completed, "Appointment completed"),
            (messages.appointment_no_show, "No-show"),
        )
        for build_message, title in cases:
            with self.subTest(message=build_message.__name__):
                text = build_message(self.appointment)

                self.assertIn(f"{title} #{self.appointment.pk}", text)
                self.assert_has_appointment_details(text)

    def test_patient_without_name_is_shown_by_email(self):
        self.user.first_name = ""
        self.user.last_name = ""

        text = messages.appointment_booked(self.appointment)

        self.assertIn("Patient: patient@example.com\n", text)


class PaymentMessagesTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.payment = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.NO_SHOW_FEE,
            session_id="sess_test_123",
            session_url="https://checkout.stripe.com/pay/sess_test_123",
            money_to_pay=Decimal("960.00"),
        )

    def test_payment_succeeded_has_payment_details(self):
        text = messages.payment_succeeded(self.payment)

        self.assertIn(f"Payment #{self.payment.pk} succeeded", text)
        self.assertIn("Type: No-show fee", text)
        self.assertIn("Amount: 960.00", text)
        self.assertIn(f"Appointment: #{self.appointment.pk}", text)

    def test_payment_succeeded_has_patient_and_doctor_without_price(self):
        text = messages.payment_succeeded(self.payment)

        self.assertIn("Patient: Ivan Petrenko (patient@example.com)", text)
        self.assertIn("Doctor: Olena Kovalenko", text)
        self.assertNotIn("Price:", text)
