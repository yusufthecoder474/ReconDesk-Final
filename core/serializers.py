from rest_framework import serializers
from .models import Invoice, Payment


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "customer",
            "issued_on",
            "due_on",
            "amount",
            "finalized",
        ]
        read_only_fields = ["finalized"]

    def validate(self, attrs):
        if (
            attrs.get("due_on")
            and attrs.get("issued_on")
            and attrs["due_on"] < attrs["issued_on"]
        ):
            raise serializers.ValidationError(
                {"due_on": "Due date must be on or after issue date"}
            )
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "customer", "reference", "invoice_hint", "paid_on", "amount"]
