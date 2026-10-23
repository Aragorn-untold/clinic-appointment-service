from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiResponse
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import RetrieveModelMixin, DestroyModelMixin
from rest_framework.viewsets import GenericViewSet

from core.permissions import IsAdminOrReadOnly
from doctor_slots.models import DoctorSlot
from doctor_slots.serializers import DoctorSlotSerializer


@extend_schema_view(
    destroy=extend_schema(responses={204: None, 400: OpenApiResponse(description="Slot has appointments")})
)
class DoctorSlotsViewSet(RetrieveModelMixin, DestroyModelMixin, GenericViewSet):
    queryset = DoctorSlot.objects.all()
    serializer_class = DoctorSlotSerializer
    permission_classes = (IsAdminOrReadOnly,)

    def perform_destroy(self, instance):
        if instance.appointments.exists():
            raise ValidationError("Cannot delete a slot that has appointments. Cancel or move them first.")
        instance.delete()
