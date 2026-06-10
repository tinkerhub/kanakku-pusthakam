from rest_framework import serializers


class RequestItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class RequestSubmitSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    requested_for = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    items = RequestItemInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        product_ids = [item["product_id"] for item in attrs["items"]]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                {"items": "Duplicate product_id values are not allowed."}
            )
        return attrs


class RequestSubmitResponseSerializer(serializers.Serializer):
    public_token = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)


class PublicRequestItemStatusSerializer(serializers.Serializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    requested_quantity = serializers.IntegerField(read_only=True)


class PublicRequestStatusSerializer(serializers.Serializer):
    # Public + token-addressable: deliberately omits requester_username. The check-in
    # identity may be a name / email / badge / student id (PII), and the requester does
    # not need their own identity echoed back to learn a request's status.
    status = serializers.CharField(read_only=True)
    rejection_reason = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    items = PublicRequestItemStatusSerializer(many=True, read_only=True)


class CheckinVerifyRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField()


class CheckinVerifyResponseSerializer(serializers.Serializer):
    username = serializers.CharField()


class AdminRequestItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    requested_quantity = serializers.IntegerField(read_only=True)
    accepted_quantity = serializers.IntegerField(read_only=True)


class AdminRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    makerspace_id = serializers.IntegerField(read_only=True)
    requester_username = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    requested_for = serializers.CharField(read_only=True)
    rejection_reason = serializers.CharField(read_only=True)
    accepted_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    items = AdminRequestItemSerializer(many=True, read_only=True)


class RejectRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)
