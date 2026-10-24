from django.utils import timezone

TIME_FORMAT = "%d.%m.%Y %H:%M"


def user_patient(user) -> str:
    name = user.get_full_name()
    return f"{name} ({user.email})" if name else user.email


def appoint_details(appointment) -> list[str]:
    slot = appointment.doctor_slot
    return [
        f"Patient: {user_patient(appointment.patient)}",
        f"Doctor: {slot.doctor}",
        f"Time: {timezone.localtime(slot.start):{TIME_FORMAT}}",
        f"Price: {appointment.price}",
    ]


def build_message_for_me(title: str, appointment) -> str:
    return "\n".join([f"{title} #{appointment.pk}", *appoint_details(appointment)])


def appointment_booked(appointment) -> str:
    return build_message_for_me("New appointment", appointment)


def appointment_cancelled(appointment) -> str:
    return build_message_for_me("Appointment cancelled", appointment)


def appointment_completed(appointment) -> str:
    return build_message_for_me("Appointment completed", appointment)


def appointment_no_show(appointment) -> str:
    return build_message_for_me("No-show", appointment)


def payment_succeeded(payment) -> str:
    appointment = payment.appointment
    return "\n".join(
        [
            f"Payment #{payment.pk} succeeded",
            f"Type: {payment.get_type_display()}",
            f"Amount: {payment.money_to_pay}",
            f"Appointment: #{appointment.pk}",
            *appoint_details(appointment)[:3],
        ]
    )
