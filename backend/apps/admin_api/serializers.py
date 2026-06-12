from rest_framework import serializers

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct, PublicAvailabilityMode, TrackingMode
from apps.makerspaces.models import Makerspace, MakerspaceMembership


class MakerspaceSerializer(serializers.ModelSerializer):
    telegram_bot_token = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )
    smtp_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )
    telegram_bot_token_set = serializers.SerializerMethodField()
    smtp_password_set = serializers.SerializerMethodField()

    class Meta:
        model = Makerspace
        fields = [
            "id",
            "name",
            "public_code",
            "slug",
            "location",
            "public_inventory_enabled",
            "public_api_key",
            "cors_allowed_origins",
            "telegram_group_chat_id",
            "telegram_bot_token",
            "telegram_bot_token_set",
            "smtp_host",
            "smtp_port",
            "smtp_username",
            "smtp_password",
            "smtp_password_set",
            "smtp_use_tls",
            "smtp_from_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "public_api_key",
            "telegram_bot_token_set",
            "smtp_password_set",
            "created_at",
            "updated_at",
        ]

    def get_telegram_bot_token_set(self, obj) -> bool:
        return bool(obj.telegram_bot_token)

    def get_smtp_password_set(self, obj) -> bool:
        return bool(obj.smtp_password)

    def validate_public_code(self, value):
        return value.upper()


class InventoryProductAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryProduct
        fields = [
            "id",
            "makerspace",
            "box",
            "name",
            "description",
            "tracking_mode",
            "total_quantity",
            "available_quantity",
            "reserved_quantity",
            "issued_quantity",
            "damaged_quantity",
            "lost_quantity",
            "is_public",
            "public_self_checkout_enabled",
            "show_public_count",
            "public_availability_mode",
            "storage_location",
            "is_archived",
            "created_at",
            "updated_at",
        ]
        # makerspace is read-only: it is set from the URL scope on create and must
        # never be reassigned on PATCH, or a manager in one tenant could move a
        # product into another. Box scope is enforced in the view (it knows the
        # authoritative makerspace).
        read_only_fields = ["id", "makerspace", "created_at", "updated_at"]

    def validate_tracking_mode(self, value):
        if value not in TrackingMode.values:
            raise serializers.ValidationError("Invalid tracking mode.")
        return value

    def validate_public_availability_mode(self, value):
        if value not in PublicAvailabilityMode.values:
            raise serializers.ValidationError("Invalid public availability mode.")
        return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "access_status",
            "restriction_reason",
            "telegram_user_id",
            "external_checkin_user_id",
            "is_active",
        ]
        read_only_fields = ["id"]


class StaffMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    makerspace_id = serializers.IntegerField(source="makerspace.id")
    makerspace_slug = serializers.SlugField(source="makerspace.slug")

    class Meta:
        model = MakerspaceMembership
        fields = ["id", "user", "makerspace_id", "makerspace_slug", "role", "created_at"]


class StaffCreateSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    makerspace_id = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=[
            MakerspaceMembership.Role.SPACE_MANAGER,
            MakerspaceMembership.Role.GUEST_ADMIN,
            MakerspaceMembership.Role.INVENTORY_MANAGER,
            MakerspaceMembership.Role.PRINT_MANAGER,
        ]
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)


class RestrictUserSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)
    status = serializers.ChoiceField(
        choices=[User.AccessStatus.RESTRICTED, User.AccessStatus.SUSPENDED],
        default=User.AccessStatus.RESTRICTED,
    )


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


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "action",
            "makerspace",
            "target_type",
            "target_id",
            "meta",
            "created_at",
        ]
