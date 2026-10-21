from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "appointment",
        "status",
        "type",
        "money_to_pay",
        "session_id",
    )
    list_filter = ("status", "type")
    search_fields = (
        "session_id",
        "appointment__patient__email",
    )
