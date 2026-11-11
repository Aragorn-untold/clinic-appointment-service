from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment
from notifications.messages import (
    appointment_cancelled,
    appointment_completed,
    appointment_no_show,
)
from notifications.services import notify_admins
from payments.models import Payment
from payments.tasks import create_appointment_payment


def schedule_payment(appointment, payment_type: str):
    transaction.on_commit(lambda: create_appointment_payment.delay(appointment.id, payment_type))


def cancel_appointment(appointment, request=None):
    if appointment.status != Appointment.Status.BOOKED:
        raise ValueError("Only booked appointments can be cancelled.")
    time = timezone.now()
    if appointment.doctor_slot.start <= time:
        raise ValueError("The appointment has already started and can no longer be cancelled.")
    time_until_appointment = appointment.doctor_slot.start - time
    if time_until_appointment < timedelta(hours=24):
        schedule_payment(appointment, Payment.Type.CANCELLATION_FEE)
    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status"])
    notify_admins(appointment_cancelled(appointment))
    return appointment


def complete_appointment(appointment, request=None):
    if appointment.status != Appointment.Status.BOOKED:
        raise ValueError("Only booked appointments can be completed.")
    appointment.status = Appointment.Status.COMPLETED
    appointment.completed_at = timezone.now()
    appointment.save(update_fields=["status", "completed_at"])
    schedule_payment(appointment, Payment.Type.CONSULTATION)
    notify_admins(appointment_completed(appointment))
    return appointment


def mark_no_show(appointment, request=None):
    if appointment.status != Appointment.Status.BOOKED:
        raise ValueError("Only booked appointments can be marked as no-show.")
    if appointment.doctor_slot.end > timezone.now():
        raise ValueError("Only appointments that have already ended can be marked as no-show.")
    appointment.status = Appointment.Status.NO_SHOW
    appointment.save(update_fields=["status"])
    schedule_payment(appointment, Payment.Type.NO_SHOW_FEE)
    notify_admins(appointment_no_show(appointment))
    return appointment
