from django.db import models


class DoctorSlot(models.Model):
    doctor = models.ForeignKey(
        "doctors.Doctor",
        on_delete=models.CASCADE,
        related_name="slots",
    )
    start = models.DateTimeField()
    end = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "start", "end"],
                name="unique_doctor_slot_time",
            ),
        ]

    def __str__(self):
        return f"{self.doctor}: {self.start} - {self.end}"
