from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from core.permissions import IsAdminOrReadOnly
from specializations.models import Specialization
from specializations.serializers import SpecializationSerializer


@extend_schema(tags=["Specializations"])
@extend_schema_view(
    list=extend_schema(
        summary="List of specializations",
        description="Available to everyone, including anonymous users.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a specialization",
        description="Available to everyone.",
    ),
    create=extend_schema(
        summary="Create specialization",
        description="Only admin. `name` and `code` are unique",
    ),
    update=extend_schema(
        summary="Fully update a specialization",
        description="Only admin.",
    ),
    partial_update=extend_schema(
        summary="Partially update a specialization",
        description="Only admin.",
    ),
    destroy=extend_schema(
        summary="Delete specialization",
        description="Only admin.",
    ),
)
@method_decorator(cache_page(60 * 15, key_prefix="specializations"), name="list")
class SpecializationViewSet(viewsets.ModelViewSet):
    queryset = Specialization.objects.all()
    serializer_class = SpecializationSerializer
    permission_classes = [IsAdminOrReadOnly]
