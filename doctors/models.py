from django.db import models


class Doctor(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    specializations = models.ManyToManyField(
        "specializations.Specialization",
        related_name="doctors",
    )
    price_per_visit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
