from rest_framework import serializers

from specializations.models import Specialization


class SpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialization
        fields = ["id", "name", "code", "description"]
