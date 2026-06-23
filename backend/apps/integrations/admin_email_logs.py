from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.integrations.models import EmailLog
from config.admin_access import SuperuserOnlyModelAdmin


@admin.register(EmailLog)
class EmailLogAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("created_at", "to_email", "stream", "event", "status", "makerspace")
    list_filter = ("status", "stream", "makerspace")
    search_fields = ("to_email", "subject", "event", "error", "makerspace__name")
    # Bodies (text_body/html_body) are deliberately NOT exposed here: a body can carry
    # PII and, for non-persisted sends, a live recovery token. Same rule the REST
    # serializer follows — bodies never serialized to API or admin — applies to /control/.
    readonly_fields = (
        "makerspace",
        "to_email",
        "subject",
        "stream",
        "event",
        "audience",
        "connection_kind",
        "status",
        "error",
        "attempts",
        "body_stored",
        "created_at",
        "updated_at",
        "sent_at",
    )
    fields = readonly_fields

    @admin.display(boolean=True, description="Body stored")
    def body_stored(self, obj):
        return bool(obj.text_body or obj.html_body)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
