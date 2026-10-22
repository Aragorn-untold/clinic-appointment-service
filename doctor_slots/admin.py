from django.contrib import admin

from .models import DoctorSlot


@admin.register(DoctorSlot)
class DoctorSlotAdmin(admin.ModelAdmin):
    list_display = ("id", "doctor", "start", "end")
    list_filter = ("doctor",)
    search_fields = ("doctor__first_name", "doctor__last_name")
    ordering = ("start",)
