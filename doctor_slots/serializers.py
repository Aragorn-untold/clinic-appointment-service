from django.utils import timezone
from rest_framework import serializers

from doctor_slots.models import DoctorSlot
from doctors.serializers import DoctorDetailSerializer


class DoctorSlotDetailSerializer(serializers.ModelSerializer):
    doctor = DoctorDetailSerializer(read_only=True)

    class Meta:
        model = DoctorSlot
        fields = ["id", "doctor", "start", "end"]


class DoctorSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorSlot
        fields = ("id", "doctor", "start", "end")
        read_only_fields = fields


class BulkSlotCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    slot_length_minutes = serializers.IntegerField(
        min_value=5,
        max_value=240,
    )

    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Cannot create slots for a past date.")
        return value

    def validate(self, attrs):
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError("end_time must be later than start_time.")
        return attrs
