import logging

from celery import shared_task

from appointments.models import Appointment
from notifications.services import notify_admins
from payments.services import PaymentService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def create_appointment_payment(self, appoint_id: int, payment_type: str):
    appoint = Appointment.objects.get(pk=appoint_id)
    try:
        PaymentService.create_payment_for_appointment(
            appoint, payment_type, idempotency_key=f"payment-task-{self.request.id}"
        )
    except RuntimeError as eee:  # Stripe is down
        if self.request.retries >= self.max_retries:
            logger.error("Gave up creating %s payment for appointment %s", payment_type, appoint_id)
            notify_admins(f"Could not create {payment_type} payment for appointment #{appoint_id}: {eee}")
            raise
        raise self.retry(exc=eee, countdown=min(30 * 2**self.request.retries, 1800)) from eee


@shared_task
def expire_stale_payment_sessions() -> int:
    return PaymentService.expire_stale_sessions()
