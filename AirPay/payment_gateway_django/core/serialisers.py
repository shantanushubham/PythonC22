from rest_framework import serializers

class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "unavailable"])
    service = serializers.CharField()
    database = serializers.CharField(help_text="`ok` or `unavailable`.")


class FieldErrorSerializer(serializers.Serializer):
    field = serializers.CharField(help_text="The field at fault. Nested fields look like `items.1.qty`.")
    message = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    """The body of every error response."""

    success = serializers.BooleanField(default=False)
    message = serializers.CharField()


class ValidationErrorSerializer(ErrorSerializer):
    errors = FieldErrorSerializer(many=True)
