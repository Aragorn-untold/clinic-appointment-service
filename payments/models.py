from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        EXPIRED = "EXPIRED", "Expired"

    class Type(models.TextChoices):
        CONSULTATION = "CONSULTATION", "Consultation"
        CANCELLATION_FEE = "CANCELLATION_FEE", "Cancellation fee"
        NO_SHOW_FEE = "NO_SHOW_FEE", "No-show fee"

    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
    )
    # Stripe Checkout URLs are often longer than the default 200 characters
    session_url = models.URLField(max_length=2048)
    session_id = models.CharField(max_length=255, unique=True)
    money_to_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    def __str__(self):
        return f"Payment #{self.pk} — {self.status}"
