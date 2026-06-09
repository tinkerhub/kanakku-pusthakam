import segno
from django.contrib import admin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from apps.boxes.models import Box


@admin.register(Box)
class BoxAdmin(ModelAdmin):
    list_display = ("label", "makerspace", "parent", "code", "is_active", "updated_at")
    list_filter = ("makerspace", "is_active")
    search_fields = ("label", "code", "location")
    autocomplete_fields = ("makerspace", "parent")
    readonly_fields = ("code", "qr_preview", "created_at", "updated_at")

    def qr_preview(self, obj):
        if not obj or not obj.pk:
            return "(save first to generate the QR)"
        return mark_safe(segno.make(obj.code).svg_inline(scale=4))

    qr_preview.short_description = "QR tag"
