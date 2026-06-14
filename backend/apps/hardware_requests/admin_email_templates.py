from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.hardware_requests.models import HardwareEmailTemplate
from config.admin_access import SuperuserOnlyModelAdmin


@admin.register(HardwareEmailTemplate)
class HardwareEmailTemplateAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("makerspace", "key", "subject", "is_active", "updated_at")
    list_filter = ("key", "is_active", "makerspace")
    search_fields = ("subject", "text_body", "html_body", "makerspace__name")
    autocomplete_fields = ("makerspace",)
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "makerspace",
        "key",
        "subject",
        "text_body",
        "html_body",
        "is_active",
        "created_at",
        "updated_at",
    )
