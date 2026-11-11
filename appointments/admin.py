from django.contrib import admin, messages
from django.db import transaction

from appointments import services

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
    readonly_fields = ("doctor_slot", "patient", "status", "booked_at", "completed_at", "price")
    actions = ("complete_appointments", "cancel_appointments", "mark_no_show_appointments")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # No rights for you

    def _run_service(self, request, queryset, service, done_label):
        done, failde = 0, []
        for appoint_id in queryset.values_list("id", flat=True):
            try:
                with transaction.atomic():
                    appointment = Appointment.objects.select_for_update().get(id=appoint_id)
                    service(appointment, request)
            except ValueError as eee:
                failde.append(f"{appoint_id}: {eee}")
            else:
                done += 1
        if done:
            self.message_user(request, f"{done} appointments {done_label}", messages.SUCCESS)
        for er in failde:
            self.message_user(request, er, messages.ERROR)

    @admin.action(description="Complete selected appointments")
    def complete_appointments(self, request, queryset):
        self._run_service(request, queryset, services.complete_appointment, "completed")

    @admin.action(description="Cancel selected appointments")
    def cancel_appointments(self, request, queryset):
        self._run_service(request, queryset, services.cancel_appointment, "cancelled")

    @admin.action(description="Mark selected appointments as no-show")
    def mark_no_show_appointments(self, request, queryset):
        self._run_service(request, queryset, services.mark_no_show, "marked as no-show")
