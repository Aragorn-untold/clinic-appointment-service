from rest_framework import serializers

from payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
<<<<<<< HEAD
        fields = [
            "id",
            "appointment",
            "type",
            "status",
            "session_id",
            "session_url",
            "money_to_pay",
        ]
        read_only_fields = fields
=======
        fields = ("id", "appointment", "status", "type", "session_url", "session_id", "money_to_pay")
>>>>>>> dd05545c72bcc2a1586771fd3d8cf105d89e0661
