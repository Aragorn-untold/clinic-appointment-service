def appointment_booked(appointment) -> str:
    return f"Appointment #{appointment.pk} booked"


def appointment_cancelled(appointment) -> str:
    return f"Appointment #{appointment.pk} cancelled"


def appointment_completed(appointment) -> str:
    return f"Appointment #{appointment.pk} completed"


def appointment_no_show(appointment) -> str:
    return f"Appointment #{appointment.pk} no-show"


def payment_succeeded(payment) -> str:
    return f"Payment #{payment.pk} succeeded"
