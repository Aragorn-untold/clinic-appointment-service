
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
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")),
                name="doctor_slot_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["doctor", "start", "end"],
                name="unique_doctor_slot_time",
            ),
        ]

    def save(self, *args, **kwargs):
        overlapping_slots = DoctorSlot.objects.filter(
            doctor=self.doctor,
            start__lt=self.end,
            end__gt=self.start,
        ).exclude(pk=self.pk)

        if overlapping_slots.exists():
            raise ValueError("Doctor already has an overlapping slot.")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.doctor}: {self.start} - {self.end}"
