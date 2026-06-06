from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateTimeFilter,
    RangeNumericFilter,
    RelatedDropdownFilter,
)

from apps.inventory.models import InventoryProduct


@admin.register(InventoryProduct)
class InventoryProductAdmin(ModelAdmin):
    list_display = (
        "name",
        "makerspace",
        "box",
        "is_public",
        "public_availability_mode",
        "available_quantity",
        "total_quantity",
        "is_archived",
        "updated_at",
    )
    list_filter = (
        ("makerspace", RelatedDropdownFilter),
        ("box", RelatedDropdownFilter),
        ("public_availability_mode", ChoicesDropdownFilter),
        ("is_public", BooleanRadioFilter),
        ("is_archived", BooleanRadioFilter),
        ("show_public_count", BooleanRadioFilter),
        ("available_quantity", RangeNumericFilter),
        ("total_quantity", RangeNumericFilter),
        ("updated_at", RangeDateTimeFilter),
    )
    search_fields = ("name", "description", "makerspace__name", "makerspace__slug")
    # Admin autocomplete is not yet tenant-scoped; deferred to Phase 2 RBAC.
    # InventoryProduct.clean() is the safety net.
    autocomplete_fields = ("makerspace", "box")
    list_select_related = ("makerspace", "box")
    ordering = ("name",)
    date_hierarchy = "updated_at"
    list_filter_submit = True
    list_per_page = 50
