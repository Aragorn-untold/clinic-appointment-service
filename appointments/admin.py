from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "doctor_slot",
        "patient",
        "status",
        "booked_at",
        "price",
    )
    list_filter = ("status", "booked_at")
    search_fields = (
        "patient__email",
        "patient__first_name",
        "patient__last_name",
    )
    ordering = ("-booked_at",)
