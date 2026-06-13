from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateTimeFilter,
    RangeNumericFilter,
    RelatedDropdownFilter,
)

from apps.inventory.models import Category, InventoryAsset, InventoryProduct


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "makerspace", "display_order", "slug")
    list_filter = (("makerspace", RelatedDropdownFilter),)
    search_fields = ("name", "slug", "makerspace__name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("makerspace",)
    ordering = ("display_order", "name")


@admin.register(InventoryProduct)
class InventoryProductAdmin(ModelAdmin):
    list_display = (
        "name",
        "category",
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
        ("category", RelatedDropdownFilter),
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
    autocomplete_fields = ("makerspace", "category", "box")
    list_select_related = ("makerspace", "category", "box")
    ordering = ("name",)
    date_hierarchy = "updated_at"
    list_filter_submit = True
    list_per_page = 50


@admin.register(InventoryAsset)
class InventoryAssetAdmin(ModelAdmin):
    list_display = ("asset_tag", "product", "makerspace", "box", "status", "updated_at")
    list_filter = ("makerspace", "status")
    search_fields = ("asset_tag", "serial_number", "product__name")
    autocomplete_fields = ("makerspace", "product", "box")
    list_select_related = ("makerspace", "product", "box")
