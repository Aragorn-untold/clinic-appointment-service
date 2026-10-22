from django.contrib import admin

from .models import Doctor


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "price_per_visit")
    search_fields = ("first_name", "last_name")
    list_filter = ("specializations",)
