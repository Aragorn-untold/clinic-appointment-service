from django.db import transaction
from django.db.models import OuterRef, Exists
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from appointments.models import Appointment
from core.permissions import IsAdminOrReadOnly
from doctor_slots.models import DoctorSlot
from doctor_slots.serializers import BulkSlotCreateSerializer, DoctorSlotSerializer
from doctors.models import Doctor
from doctors.serializers import DoctorSerializer
from doctors.services import generate_slots


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.prefetch_related("specializations").order_by("last_name", "first_name")
    serializer_class = DoctorSerializer
    permission_classes = (IsAdminOrReadOnly,)

    def get_queryset(self):
        queryset = super().get_queryset()
        specialization = self.request.query_params.get("specialization")

        if specialization:
            if specialization.isdigit():
                queryset = queryset.filter(specializations__pk=specialization)
            else:
                queryset = queryset.filter(specializations__code=specialization)

        return queryset

    @extend_schema(
        request=BulkSlotCreateSerializer,
        responses={201: DoctorSlotSerializer(many=True)},
        description=(
            "Bulk-create slots for the doctor. Slots overlapping existing "
            "ones are skipped. Returns only the created slots."
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="slots",
        serializer_class=BulkSlotCreateSerializer,
    )
    def slots(self, request, pk=None):
        doctor = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        candidates = [
            (timezone.make_aware(start), timezone.make_aware(end))
            for start, end in generate_slots(
                data["date"],
                data["start_time"],
                data["end_time"],
                data["slot_length_minutes"],
            )
        ]

        if not candidates:
            return Response([], status=status.HTTP_201_CREATED)

        day_start, day_end = candidates[0][0], candidates[-1][1]

        with transaction.atomic():
            # Lock the doctor row so concurrent requests can't create overlapping slots
            Doctor.objects.select_for_update().get(pk=doctor.pk)
            existing = list(
                DoctorSlot.objects.filter(doctor=doctor, start__lt=day_end, end__gt=day_start).values_list(
                    "start", "end"
                )
            )

            new_slots = [
                DoctorSlot(doctor=doctor, start=start, end=end)
                for start, end in candidates
                if not any(start < ex_end and end > ex_start for ex_start, ex_end in existing)
            ]
            created = DoctorSlot.objects.bulk_create(new_slots)

        return Response(
            DoctorSlotSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    def _parse_datetime_param(self, name):
        value = self.request.query_params.get(name)
        if not value:
            return None

        try:
            parsed = parse_datetime(value)
        except ValueError:  # правильний формат, неможлива дата
            parsed = None
        if parsed is None:  # «сміття»
            raise ValidationError({name: ["Invalid date"]})

        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed

    @extend_schema(
        summary="List doctor's slots",
        responses=DoctorSlotSerializer(many=True),
        parameters=[
            OpenApiParameter(
                name="from",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                        "Only slots starting at or after this moment (ISO 8601), "
                        "e.g. `2026-10-30T09:00`. Without a time zone offset the "
                        "project time zone is used."
                ),
            ),
            OpenApiParameter(
                name="to",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                        "Only slots ending at or before this moment (ISO 8601), "
                        "e.g. `2026-10-30T13:00`. Without a time zone offset the "
                        "project time zone is used."
                ),
            ),
            OpenApiParameter(
                name="available_only",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                        "`true` returns only slots without a BOOKED appointment. "
                        "Any other value or no value returns all slots."
                ),
            ),
        ],
    )
    @slots.mapping.get
    def get_slots(self, request, pk=None):
        doctor = self.get_object()
        doctor_slots = doctor.slots.order_by("start")
        from_time = self._parse_datetime_param("from")
        to_time = self._parse_datetime_param("to")
        available_only = request.query_params.get("available_only", "").lower() == "true"

        if from_time:
            doctor_slots = doctor_slots.filter(start__gte=from_time)

        if to_time:
            doctor_slots = doctor_slots.filter(end__lte=to_time)

        if available_only:
            booked = Appointment.objects.filter(
                doctor_slot=OuterRef("pk"),
                status=Appointment.Status.BOOKED,
            )
            doctor_slots = doctor_slots.annotate(is_booked=Exists(booked)).filter(
                is_booked=False
            )

        return Response(
            DoctorSlotSerializer(doctor_slots, many=True).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="specialization",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Filter doctors by specialization. Accepts either the "
                    "specialization id or its code, e.g. "
                    "`?specialization=3` or `?specialization=cardiology`. "
                    "A numeric value is treated as an id."
                ),
                required=False,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
