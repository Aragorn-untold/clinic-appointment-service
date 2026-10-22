from rest_framework import serializers

from doctor_slots.models import DoctorSlot
from doctors.serializers import DoctorDetailSerializer


class DoctorSlotDetailSerializer(serializers.ModelSerializer):
    doctor = DoctorDetailSerializer(read_only=True)

    class Meta:
        model = DoctorSlot
        fields = ["id", "doctor", "start", "end"]
