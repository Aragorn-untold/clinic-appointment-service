from rest_framework import serializers

from appointments.models import Appointment


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


class DoctorDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    specializations = serializers.StringRelatedField(many=True)


class DoctorSlotDetailSerializer(serializers.ModelSerializer):
    doctor = DoctorDetailSerializer(read_only=True)

    class Meta:
        model = Appointment._meta.get_field("doctor_slot").related_model
        fields = ["id", "doctor", "start", "end"]


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
