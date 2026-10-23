from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from core.permissions import IsAdminOrReadOnly
from specializations.models import Specialization
from specializations.serializers import SpecializationSerializer


@extend_schema(tags=["Specializations"])
@extend_schema_view(
    list=extend_schema(
        summary="Список спеціалізацій",
        description="Доступно всім, включно з анонімними користувачами.",
    ),
    retrieve=extend_schema(
        summary="Отримати спеціалізацію",
        description="Доступно всім.",
    ),
    create=extend_schema(
        summary="Створити спеціалізацію",
        description="Тільки адміністратор. `name` і `code` унікальні",
    ),
    update=extend_schema(
        summary="Повністю оновити спеціалізацію",
        description="Тільки адміністратор.",
    ),
    partial_update=extend_schema(
        summary="Частково оновити спеціалізацію",
        description="Тільки адміністратор.",
    ),
    destroy=extend_schema(
        summary="Видалити спеціалізацію",
        description="Тільки адміністратор.",
    ),
)
class SpecializationViewSet(viewsets.ModelViewSet):
    queryset = Specialization.objects.all()
    serializer_class = SpecializationSerializer
    permission_classes = [IsAdminOrReadOnly]
