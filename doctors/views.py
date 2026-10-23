from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets

from core.permissions import IsAdminOrReadOnly
from doctors.models import Doctor
from doctors.serializers import DoctorSerializer


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
