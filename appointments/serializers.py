from rest_framework import serializers

from appointments.models import Appointment
from doctor_slots.serializers import DoctorSlotDetailSerializer


class AppointmentListSerializer(serializers.ModelSerializer):
    doctor = serializers.CharField(
        source="doctor_slot.doctor",
        read_only=True,
    )
    start = serializers.DateTimeField(
        source="doctor_slot.start",
        read_only=True,
    )
    end = serializers.DateTimeField(
        source="doctor_slot.end",
        read_only=True,
    )

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "doctor",
            "start",
            "end",
            "status",
            "price",
        ]


class AppointmentDetailSerializer(serializers.ModelSerializer):
    doctor_slot = DoctorSlotDetailSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "doctor_slot",
            "status",
            "booked_at",
            "completed_at",
            "price",
        ]
