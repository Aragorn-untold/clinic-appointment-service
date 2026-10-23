from django.contrib.gis import serializers
from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

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

        day_start, day_end = candidates[0][0], candidates[-1][1]
        existing = list(
            DoctorSlot.objects.filter(
                doctor=doctor, start__lt=day_end, end__gt=day_start
            ).values_list("start", "end")
        )

        new_slots = [
            DoctorSlot(doctor=doctor, start=start, end=end)
            for start, end in candidates
            if not any(start < ex_end and end > ex_start for ex_start, ex_end in existing)
        ]

        with transaction.atomic():
            created = DoctorSlot.objects.bulk_create(new_slots)

        return Response(
            DoctorSlotSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
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
