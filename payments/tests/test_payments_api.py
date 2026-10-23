from decimal import Decimal

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
