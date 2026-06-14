from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.printing.models import PrintBucket
from config.admin_access import SuperuserOnlyModelAdmin


@admin.register(PrintBucket)
class PrintBucketAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("name", "makerspace", "is_active", "updated_at")
    list_filter = ("is_active", "makerspace")
    search_fields = ("name", "description", "makerspace__name", "makerspace__slug")
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "makerspace",
        "name",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    )
