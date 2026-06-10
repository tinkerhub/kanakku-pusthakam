from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.accounts import rbac
from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem

MANAGER_ROLES = (User.Role.SUPERADMIN, User.Role.ADMIN)


class HardwareRequestItemInline(TabularInline):
    model = HardwareRequestItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product",
        "requested_quantity",
        "accepted_quantity",
        "issued_quantity",
        "returned_quantity",
        "damaged_quantity",
        "missing_quantity",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(HardwareRequest)
class HardwareRequestAdmin(ModelAdmin):
    list_display = ("id", "status", "makerspace", "requester_username", "created_at")
    list_filter = ("status", "makerspace")
    search_fields = (
        "requester_username",
        "requested_for",
        "rejection_reason",
        "items__product__name",
    )
    readonly_fields = (
        "makerspace",
        "requester",
        "requester_username",
        "status",
        "requested_for",
        "rejection_reason",
        "accepted_by",
        "accepted_at",
        "closed_by",
        "closed_at",
        "public_token",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields
    inlines = [HardwareRequestItemInline]

    def has_module_permission(self, request):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.access_status == User.AccessStatus.ACTIVE
            and (user.is_superuser or user.role in MANAGER_ROLES)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return rbac.scope_by_action(
            request.user,
            rbac.Action.ACCEPT_REQUEST,
            super()
            .get_queryset(request)
            .select_related("makerspace", "requester", "accepted_by", "closed_by"),
        )
