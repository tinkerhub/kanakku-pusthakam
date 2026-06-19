from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.inventory import public_image_storage
from apps.inventory.public_availability import get_public_availability


AVAILABILITY_SCHEMA = {
    "type": "object",
    "nullable": True,
    "properties": {
        "mode": {
            "type": "string",
            "enum": ["status_only", "exact_count"],
        },
        "label": {
            "type": "string",
            "enum": ["Available", "Limited", "Unavailable"],
        },
        "count": {"type": "integer", "minimum": 0},
    },
    "required": ["mode"],
}


class PublicProductSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    category_id = serializers.IntegerField(
        source="category.id",
        read_only=True,
        allow_null=True,
    )
    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
        allow_null=True,
    )
    category_slug = serializers.CharField(
        source="category.slug",
        read_only=True,
        allow_null=True,
    )
    availability = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    @extend_schema_field(AVAILABILITY_SCHEMA)
    def get_availability(self, product):
        return get_public_availability(product)

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_image_url(self, product):
        return public_image_storage.public_url(product.image_key) or None


class PublicCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    display_order = serializers.IntegerField(read_only=True)
    icon = serializers.CharField(read_only=True)
    product_count = serializers.IntegerField(read_only=True)


class PublicMakerspaceSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    public_code = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    location = serializers.CharField(read_only=True)
    logo_url = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_logo_url(self, makerspace):
        return public_image_storage.public_url(makerspace.logo_key) or None

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_cover_image_url(self, makerspace):
        return public_image_storage.public_url(makerspace.cover_image_key) or None
