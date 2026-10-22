from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from appointments.models import Appointment
from appointments.serializers import (
    AppointmentDetailSerializer,
    AppointmentListSerializer,
)


class AppointmentViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Appointment.objects.select_related(
            "patient",
            "doctor_slot__doctor",
        ).prefetch_related("doctor_slot__doctor__specializations")

        if not self.request.user.is_staff:
            queryset = queryset.filter(patient=self.request.user)

        params = self.request.query_params

        patient_id = params.get("patient_id")
        if patient_id:
            if not patient_id.isdigit():
                raise ValidationError({"patient_id": "Must be a "
                                                     "positive integer."})
            queryset = queryset.filter(patient_id=patient_id)

        doctor_id = params.get("doctor_id")
        if doctor_id:
            if not doctor_id.isdigit():
                raise ValidationError({"doctor_id": "Must be a "
                                                    "positive integer."})
            queryset = queryset.filter(doctor_slot__doctor_id=doctor_id)

        status = params.get("status")
        if status:
            valid_statuses = Appointment.Status.values
            if status not in valid_statuses:
                raise ValidationError({"status": "Invalid "
                                                 "appointment status."})
            queryset = queryset.filter(status=status)

        for param, lookup, comparison in (
            ("from", "gte", "date"),
            ("to", "lte", "date"),
        ):
            value = params.get(param)
            if not value:
                continue

            parsed_datetime = parse_datetime(value)
            if parsed_datetime:
                queryset = queryset.filter(
                    **{f"doctor_slot__start__{lookup}": parsed_datetime}
                )
                continue

            parsed_date = parse_date(value)
            if not parsed_date:
                raise ValidationError({param: "Use YYYY-MM-DD or "
                                              "an ISO datetime."})

            queryset = queryset.filter(
                **{f"doctor_slot__start__date__{lookup}": parsed_date}
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AppointmentDetailSerializer

        return AppointmentListSerializer
