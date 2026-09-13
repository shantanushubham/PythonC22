from rest_framework import serializers

from .models import BankAccount


class BankAccountSerializer(serializers.ModelSerializer):

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "user",
            "account_no",
            "ifsc_code",
            "account_name",
            "bank_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]
