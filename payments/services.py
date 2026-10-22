from decimal import Decimal, ROUND_HALF_UP
from payments.models import Payment


class PaymentService:
    
    RATE_COEFFICIENTS = {
        Payment.Type.CONSULTATION: Decimal("1.0"),
        Payment.Type.CANCELLATION_FEE: Decimal("0.5"),
        Payment.Type.NO_SHOW_FEE: Decimal("1.2"),
    }

    @classmethod
    def calculate_amount(
        cls, 
        base_price: Decimal | str | int, 
        payment_type: str, 
        rounding: str | None = None
    ) -> Decimal:
        if not isinstance(base_price, Decimal):
            try:
                base_price = Decimal(str(base_price))
            except Exception as exc:
                raise ValueError(f"Invalid price format: {base_price}") from exc

        if base_price < Decimal("0.00"):
            raise ValueError("Price cannot be negative.")

        if payment_type not in cls.RATE_COEFFICIENTS:
            valid_types = ", ".join(cls.RATE_COEFFICIENTS.keys())
            raise ValueError(
                f"Unknown payment type '{payment_type}'. Valid: {valid_types}"
            )

        coefficient = cls.RATE_COEFFICIENTS[payment_type]
        amount = base_price * coefficient

        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def to_stripe_cents(amount: Decimal | str | int) -> int:
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
            
        cents = (amount * Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return int(cents)

    @classmethod
    def create_for_appointment(cls, appointment, payment_type, request=None):
        """
        Создаёт Stripe-сессию и Payment. Заглушка: return None.
        
        request=None -> базовый URL берётся из settings.SITE_URL
        (для Celery-задач).
        """
        return None