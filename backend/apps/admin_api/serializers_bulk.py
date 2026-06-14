from rest_framework import serializers


class BulkImportPreviewSerializer(serializers.Serializer):
    file = serializers.FileField(required=False)
    rows = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=False,
    )
    mapping = serializers.DictField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        if not attrs.get("file") and not attrs.get("rows"):
            raise serializers.ValidationError("Provide either file or rows.")
        return attrs
