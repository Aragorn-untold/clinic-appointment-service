from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from appointments import services
from appointments.models import Appointment
from appointments.serializers import (
    AppointmentCreateSerializer,
    AppointmentDetailSerializer,
    AppointmentListSerializer,
)

STATUS_CHANGE_RESPONSES = {
    200: AppointmentDetailSerializer,
    400: OpenApiResponse(description="The appointment is not BOOKED."),
    401: OpenApiResponse(description="Authentication required."),
    404: OpenApiResponse(description="Appointment not found."),
    502: OpenApiResponse(description="Stripe error while creating the payment session."),
}
ADMIN_STATUS_CHANGE_RESPONSES = {
    **STATUS_CHANGE_RESPONSES,
    403: OpenApiResponse(description="Admin only."),
}


@extend_schema(tags=["Appointments"])
@extend_schema_view(
    list=extend_schema(
        summary="List appointments",
        description="Patients see only their own appointments. Admins see all and can filter by patient.",
        parameters=[
            OpenApiParameter("patient_id", OpenApiTypes.INT, description="Filter by patient ID (useful for admins)."),
            OpenApiParameter("doctor_id", OpenApiTypes.INT, description="Filter by doctor ID."),
            OpenApiParameter(
                "status", OpenApiTypes.STR, enum=Appointment.Status.values, description="Filter by status."
            ),
            OpenApiParameter(
                "from",
                OpenApiTypes.STR,
                description="Slots starting on or after this date: `YYYY-MM-DD` or an ISO datetime.",
            ),
            OpenApiParameter(
                "to",
                OpenApiTypes.STR,
                description="Slots starting on or before this date: `YYYY-MM-DD` or an ISO datetime.",
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve an appointment",
        description="Includes the slot and all payments. Patients can only open their own appointments.",
    ),
    create=extend_schema(
        summary="Book an appointment",
        description=(
            "Books a slot for the current user. The slot must be in the future and not already booked. "
            "The price is taken from the doctor. Rejected if the patient has a PENDING or EXPIRED payment."
        ),
    ),
    cancel=extend_schema(
        summary="Cancel an appointment",
        description=(
            "Owner or admin. Only BOOKED appointments can be cancelled. Cancelling less than 24 hours "
            "before the start creates a cancellation fee payment (50% of the price)."
        ),
        request=None,
        responses=STATUS_CHANGE_RESPONSES,
    ),
    complete=extend_schema(
        summary="Complete an appointment",
        description="Admin only. Marks a BOOKED appointment as COMPLETED and creates a consultation payment.",
        request=None,
        responses=ADMIN_STATUS_CHANGE_RESPONSES,
    ),
    no_show=extend_schema(
        summary="Mark an appointment as no-show",
        description="Admin only. Marks a BOOKED appointment as NO_SHOW and creates a no-show fee payment (120%).",
        request=None,
        responses=ADMIN_STATUS_CHANGE_RESPONSES,
    ),
)
class AppointmentViewSet(ModelViewSet):
    http_method_names = ["get", "post", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Appointment.objects.none()
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
                raise ValidationError({"patient_id": "Must be a positive integer."})
            queryset = queryset.filter(patient_id=patient_id)

        doctor_id = params.get("doctor_id")
        if doctor_id:
            if not doctor_id.isdigit():
                raise ValidationError({"doctor_id": "Must be a positive integer."})
            queryset = queryset.filter(doctor_slot__doctor_id=doctor_id)

        status = params.get("status")
        if status:
            valid_statuses = Appointment.Status.values
            if status not in valid_statuses:
                raise ValidationError({"status": "Invalid appointment status."})
            queryset = queryset.filter(status=status)

        for param, lookup, _comparison in (
            ("from", "gte", "date"),
            ("to", "lte", "date"),
        ):
            value = params.get(param)
            if not value:
                continue

            parsed_datetime = parse_datetime(value)
            if parsed_datetime:
                queryset = queryset.filter(**{f"doctor_slot__start__{lookup}": parsed_datetime})
                continue

            parsed_date = parse_date(value)
            if not parsed_date:
                raise ValidationError({param: "Use YYYY-MM-DD or an ISO datetime."})

            queryset = queryset.filter(**{f"doctor_slot__start__date__{lookup}": parsed_date})

        return queryset

    def get_permissions(self):
        if self.action in ("complete", "no_show"):
            return [IsAdminUser()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return AppointmentCreateSerializer
        if self.action in ("retrieve", "cancel", "complete", "no_show"):
            return AppointmentDetailSerializer
        return AppointmentListSerializer

    def _change_status(self, service):
        appointment = self.get_object()
        with transaction.atomic():
            appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
            try:
                appointment = service(appointment, self.request)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
            except RuntimeError as exc:
                return Response({"detail": str(exc)}, status=http_status.HTTP_502_BAD_GATEWAY)
        return Response(self.get_serializer(appointment).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._change_status(services.cancel_appointment)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._change_status(services.complete_appointment)

    @action(detail=True, methods=["post"], url_path="no-show")
    def no_show(self, request, pk=None):
        return self._change_status(services.mark_no_show)
