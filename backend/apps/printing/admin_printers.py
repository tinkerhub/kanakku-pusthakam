from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.printing.models import PrintPrinter
from config.admin_access import SuperuserOnlyModelAdmin


@admin.register(PrintPrinter)
class PrintPrinterAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("name", "makerspace", "status", "is_active", "updated_at")
    list_filter = ("status", "is_active", "makerspace")
    search_fields = ("name", "model", "notes", "makerspace__name", "makerspace__slug")
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "makerspace",
        "name",
        "model",
        "status",
        "notes",
        "is_active",
        "created_at",
        "updated_at",
    )
