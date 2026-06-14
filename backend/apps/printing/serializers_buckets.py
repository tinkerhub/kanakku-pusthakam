from rest_framework import serializers

from apps.printing.models import PrintBucket


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PrintBucketSerializer(serializers.ModelSerializer):
    makerspace = serializers.IntegerField(source="makerspace_id", read_only=True)

    class Meta:
        model = PrintBucket
        fields = (
            "id",
            "makerspace",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
