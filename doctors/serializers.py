from typing import Any

from rest_framework import serializers
from rest_framework.relations import SlugRelatedField

from doctors.models import Doctor
from specializations.models import Specialization


class DoctorSerializer(serializers.ModelSerializer):
    specializations = SlugRelatedField(
        many=True,
        slug_field="code",
        queryset=Specialization.objects.all(),
        allow_empty=False
    )

    class Meta:
        model = Doctor
        fields = (
            "id",
            "first_name",
            "last_name",
            "specializations",
            "price_per_visit"
        )

from rest_framework import serializers


class DoctorDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    specializations = serializers.StringRelatedField(many=True)