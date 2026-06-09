import secrets

from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from apps.accounts import rbac
from apps.accounts.models import User
from apps.apiclients.models import ApiClient
from apps.makerspaces.models import Makerspace

MANAGER_ROLES = (User.Role.SUPERADMIN, User.Role.ADMIN)


def _is_superadmin(user):
    return user.is_superuser or user.role == User.Role.SUPERADMIN


@admin.register(ApiClient)
class ApiClientAdmin(ModelAdmin):
    list_display = ("label", "client_id", "makerspace", "is_active", "created_at")
    list_filter = ("is_active", "makerspace")
    readonly_fields = ("client_id", "created_by", "created_at", "updated_at")
    fields = (
        "label", "makerspace", "allowed_origins", "is_active",
        "client_id", "created_by", "created_at", "updated_at",
    )

    # Only ACTIVE superadmin + makerspace admins reach this admin at all
    # (review fixes #1 correct signatures, #2 access_status).
    def has_module_permission(self, request):
        u = getattr(request, "user", None)
        return bool(
            u and u.is_authenticated and u.is_active
            and u.access_status == User.AccessStatus.ACTIVE
            and (u.is_superuser or u.role in MANAGER_ROLES)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    # Admins see/edit only clients in their assigned makerspaces (superadmin: all).
    def get_queryset(self, request):
        return rbac.scope_by_makerspace(
            request.user, super().get_queryset(request), "makerspace_id"
        )

    # Admins can only target their own makerspaces and MUST pick one (no global client).
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "makerspace" and not _is_superadmin(request.user):
            scope = rbac.resolve_scope(request.user)
            ids = [] if scope is rbac.ALL else scope
            kwargs["queryset"] = Makerspace.objects.filter(id__in=ids)
            kwargs["required"] = True
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Generate + reveal the secret once at creation.
    def save_model(self, request, obj, form, change):
        new_secret = None
        if not change:
            obj.created_by = request.user
            new_secret = secrets.token_urlsafe(32)
            obj.set_secret(new_secret)
        super().save_model(request, obj, form, change)
        if new_secret:
            messages.warning(
                request,
                f"Client secret for {obj.client_id} (shown once - copy it now): {new_secret}",
            )
