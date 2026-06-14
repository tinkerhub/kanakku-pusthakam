from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.printing.models import FilamentSpool
from config.admin_access import SuperuserOnlyModelAdmin


@admin.register(FilamentSpool)
class FilamentSpoolAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = (
        "material",
        "color",
        "printer",
        "makerspace",
        "remaining_weight_grams",
        "is_active",
    )
    list_filter = ("material", "is_active", "makerspace", "printer")
    search_fields = (
        "material",
        "color",
        "brand",
        "lot_code",
        "printer__name",
        "makerspace__name",
    )
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "makerspace",
        "printer",
        "material",
        "color",
        "brand",
        "lot_code",
        "initial_weight_grams",
        "remaining_weight_grams",
        "is_active",
        "opened_at",
        "created_at",
        "updated_at",
    )
