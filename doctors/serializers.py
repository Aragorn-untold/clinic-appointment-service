from rest_framework import serializers


class DoctorDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    specializations = serializers.StringRelatedField(many=True)
