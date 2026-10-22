from decimal import Decimal
from django.test import SimpleTestCase
from payments.models import Payment
from payments.services import (
    calculate_payment_amount,
    amount_to_stripe_cents,
)


class PaymentCalculationTests(SimpleTestCase):

    def test_consultation_amount(self):
        """CONSULTATION: 1.0 * price."""
        price = Decimal("800.00")
        result = calculate_payment_amount(price, Payment.Type.CONSULTATION)
        self.assertEqual(result, Decimal("800.00"))

    def test_cancellation_fee_amount(self):
        """CANCELLATION_FEE: 0.5 * price."""
        price = Decimal("800.00")
        result = calculate_payment_amount(price, Payment.Type.CANCELLATION_FEE)
        self.assertEqual(result, Decimal("400.00"))

    def test_no_show_fee_amount(self):
        """NO_SHOW_FEE: 1.2 * price."""
        price = Decimal("800.00")
        result = calculate_payment_amount(price, Payment.Type.NO_SHOW_FEE)
        self.assertEqual(result, Decimal("960.00"))

    def test_rounding_precision(self):
        price = Decimal("33.33")
        result = calculate_payment_amount(price, Payment.Type.CANCELLATION_FEE)
        self.assertEqual(result, Decimal("16.67"))
        price2 = Decimal("15.55")
        result2 = calculate_payment_amount(price2, Payment.Type.NO_SHOW_FEE)
        self.assertEqual(result2, Decimal("18.66"))

    def test_zero_amount(self):
        result = calculate_payment_amount(Decimal("0.00"), Payment.Type.CONSULTATION)
        self.assertEqual(result, Decimal("0.00"))

    def test_negative_price_raises_error(self):
        with self.assertRaises(ValueError):
            calculate_payment_amount(Decimal("-100.00"), Payment.Type.CONSULTATION)

    def test_invalid_payment_type_raises_error(self):
        with self.assertRaises(ValueError):
            calculate_payment_amount(Decimal("500.00"), "INVALID_TYPE")

    def test_amount_to_stripe_cents(self):
        self.assertEqual(amount_to_stripe_cents(Decimal("10.00")), 1000)
        self.assertEqual(amount_to_stripe_cents(Decimal("10.50")), 1050)
        self.assertEqual(amount_to_stripe_cents(Decimal("0.99")), 99)
        self.assertEqual(amount_to_stripe_cents(Decimal("0.00")), 0)
