import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment
from appointments.services import mark_no_show
from notifications.services import notify_admins

logger = logging.getLogger(__name__)


@shared_task
def mark_no_shows() -> int:
    my_time = timezone.now()
    missed = list(
        Appointment.objects.filter(
            status=Appointment.Status.BOOKED,
            doctor_slot__end__lt=my_time,
        ).values_list("id", flat=True)
    )
    if not missed:
        notify_admins("No missed appointments today!")
        return 0
    marked = 0
    for appointment_id in missed:
        try:
            with transaction.atomic():
                appointment = (
                    Appointment.objects.select_for_update()
                    .filter(id=appointment_id, status=Appointment.Status.BOOKED, doctor_slot__end__lt=my_time)
                    .first()
                )
                if appointment is None:
                    continue
                mark_no_show(appointment)
        except Exception:
            logger.exception("Failed to mark appointment %s as no-show", appointment_id)
        else:
            marked += 1
    return marked
