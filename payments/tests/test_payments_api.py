from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from core.tests.base import BaseTestCase
from payments.models import Payment

PAYMENTS_LIST_URL = reverse("payments:payment-list")


class PaymentTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.payment = Payment.objects.create(
            appointment=cls.appointment,
            status="PENDING",
            type="CONSULTATION",
            session_url="https://test.com/test",
            session_id="cs_test_123",
            money_to_pay=Decimal("800.00"),
        )

    def test_list_as_user(self):
        res = self.auth_client.get(PAYMENTS_LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_detail_as_user(self):
        res = self.auth_client.get(reverse("payments:payment-detail", kwargs={"pk": self.payment.id}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_list_as_admin(self):
        res = self.admin_client.get(PAYMENTS_LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_unauthorized(self):
        res = self.client.get(PAYMENTS_LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class StripePaymentFlowTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.payment = Payment.objects.create(
            appointment=cls.appointment,
            status="PENDING",
            type="CONSULTATION",
            session_url="https://checkout.stripe.com/test",
            session_id="cs_test_mock_123",
            money_to_pay=Decimal("800.00"),
        )

    @patch("payments.views.notify_admins")
    @patch("stripe.checkout.Session.retrieve")
    def test_stripe_success_view(self, mock_stripe_retrieve, mock_notify):
        mock_stripe_retrieve.return_value = {"payment_status": "paid", "id": "cs_test_mock_123"}

        url = reverse("payments:success") + f"?session_id={self.payment.session_id}"
        response = self.auth_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PAID")

    def test_stripe_cancel_view(self):
        url = reverse("payments:cancel")
        response = self.auth_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("cancelled", response.data["message"].lower())
