from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.makerspaces.models import Makerspace, MakerspaceMembership


class MakerspaceMembershipInline(TabularInline):
    model = MakerspaceMembership
    fk_name = "makerspace"
    fields = ("user", "role")
    autocomplete_fields = ("user",)
    extra = 0


@admin.register(Makerspace)
class MakerspaceAdmin(ModelAdmin):
    list_display = (
        "name",
        "public_code",
        "slug",
        "location",
        "public_inventory_enabled",
        "updated_at",
    )
    list_filter = ("public_inventory_enabled",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "public_code", "slug", "location")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "public_code",
                    "slug",
                    "location",
                    "public_inventory_enabled",
                )
            },
        ),
    )
    inlines = (MakerspaceMembershipInline,)
