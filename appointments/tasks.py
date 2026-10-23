from celery import shared_task
from django.utils import timezone

from appointments.models import Appointment
from notifications.messages import appointment_no_show
from notifications.services import notify_admins


# TODO: STUB until task 5 (@andriikinash127) is merged.
# Then delete this function and use:
#   from appointments.services import mark_no_show
def mark_no_show(appointment: Appointment) -> Appointment:
    appointment.status = Appointment.Status.NO_SHOW
    appointment.save(update_fields=["status"])
    notify_admins(appointment_no_show(appointment))
    return appointment


@shared_task
def mark_no_shows() -> int:
    missed = list(
        Appointment.objects.filter(
            status=Appointment.Status.BOOKED,
            doctor_slot__end__lt=timezone.now(),
        )
    )

    if not missed:
        notify_admins("No missed appointments today!")
        return 0

    for appointment in missed:
        mark_no_show(appointment)

    return len(missed)
