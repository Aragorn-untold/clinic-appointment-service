from django.conf import settings
from django.db import models


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Booked"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No show"

    doctor_slot = models.ForeignKey(
        "doctor_slots.DoctorSlot",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.BOOKED,
    )
    booked_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor_slot"],
                condition=models.Q(status="BOOKED"),
                name="unique_booked_appointment_per_slot",
            ),
        ]

    def __str__(self):
        return f"{self.patient} — {self.doctor_slot}"
