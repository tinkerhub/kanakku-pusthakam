from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.template.response import TemplateResponse
from unfold.admin import ModelAdmin, TabularInline

from apps.hardware_requests.asset_link_models import HardwareRequestItemAsset
from apps.hardware_requests.handover_workflow import assign_box
from apps.hardware_requests.models import (
    HardwareEmailTemplate,
    HardwareRequest,
    HardwareRequestItem,
)
from apps.hardware_requests.return_models import RequesterAccountability, ReturnEvent
from apps.hardware_requests.request_workflow import accept_request, reject_request
from apps.hardware_requests.self_checkout_models import PublicToolLoan
from apps.hardware_requests.workflow_errors import (
    BoxUnavailable,
    BoxValidationError,
    InvalidTransition,
    RequestValidationError,
    RequesterBlocked,
)
from apps.inventory.availability import InsufficientStock
from config.admin_access import SuperuserOnlyModelAdmin

WORKFLOW_EXCEPTIONS = (
    InvalidTransition,
    RequestValidationError,
    RequesterBlocked,
    BoxUnavailable,
    BoxValidationError,
    InsufficientStock,
)


class HardwareRequestItemInline(TabularInline):
    model = HardwareRequestItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product",
        "requested_quantity",
        "accepted_quantity",
        "issued_quantity",
        "returned_quantity",
        "damaged_quantity",
        "missing_quantity",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(HardwareRequest)
class HardwareRequestAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    actions = ["accept_selected", "reject_selected", "assign_box_selected"]
    list_display = (
        "id",
        "status",
        "makerspace",
        "requester_username",
        "return_due_at",
        "created_at",
    )
    list_filter = ("status", "makerspace")
    search_fields = (
        "requester_username",
        "requested_for",
        "rejection_reason",
        "items__product__name",
    )
    readonly_fields = (
        "makerspace",
        "requester",
        "requester_username",
        "status",
        "requested_for",
        "rejection_reason",
        "accepted_by",
        "accepted_at",
        "assigned_box",
        "issued_by",
        "issued_at",
        "return_due_at",
        "return_reminder_sent_at",
        "closed_by",
        "closed_at",
        "public_token",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields
    inlines = [HardwareRequestItemInline]

    # Requests are created by the public submit flow and mutated only through the
    # workflow services (the actions below). Direct add hits required readonly fields
    # and direct delete bypasses reservation/audit/notification cleanup.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Accept selected requests")
    def accept_selected(self, request, queryset):
        success_count = 0
        for hardware_request in queryset:
            try:
                accept_request(request.user, hardware_request)
            except WORKFLOW_EXCEPTIONS as exc:
                self.message_user(
                    request,
                    f"{hardware_request.pk}: {exc}",
                    level=messages.ERROR,
                )
            else:
                success_count += 1

        if success_count:
            self.message_user(
                request,
                f"Accepted {success_count} hardware request(s).",
                level=messages.SUCCESS,
            )

    @admin.action(description="Reject selected requests (with reason)")
    def reject_selected(self, request, queryset):
        if "apply" not in request.POST:
            return self._intermediate_action_response(
                request,
                queryset,
                "admin/hardware_requests/reject_action.html",
                "Reject selected hardware requests",
                "reject_selected",
            )

        reason = request.POST.get("reason", "").strip()
        if not reason:
            self.message_user(
                request,
                "Rejection reason is required.",
                level=messages.ERROR,
            )
            return None

        success_count = 0
        for hardware_request in queryset:
            try:
                reject_request(request.user, hardware_request, reason)
            except WORKFLOW_EXCEPTIONS as exc:
                self.message_user(
                    request,
                    f"{hardware_request.pk}: {exc}",
                    level=messages.ERROR,
                )
            else:
                success_count += 1

        if success_count:
            self.message_user(
                request,
                f"Rejected {success_count} hardware request(s).",
                level=messages.SUCCESS,
            )
        return None

    @admin.action(description="Assign box to selected requests")
    def assign_box_selected(self, request, queryset):
        if "apply" not in request.POST:
            return self._intermediate_action_response(
                request,
                queryset,
                "admin/hardware_requests/assign_box_action.html",
                "Assign boxes to selected hardware requests",
                "assign_box_selected",
            )

        success_count = 0
        for hardware_request in queryset:
            box_code = request.POST.get(f"box_code_{hardware_request.pk}", "").strip()
            try:
                assign_box(request.user, hardware_request, box_code)
            except WORKFLOW_EXCEPTIONS as exc:
                self.message_user(
                    request,
                    f"{hardware_request.pk}: {exc}",
                    level=messages.ERROR,
                )
            else:
                success_count += 1

        if success_count:
            self.message_user(
                request,
                f"Assigned boxes for {success_count} hardware request(s).",
                level=messages.SUCCESS,
            )
        return None

    def _intermediate_action_response(
        self,
        request,
        queryset,
        template_name,
        title,
        action_name,
    ):
        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "queryset": queryset,
            "opts": self.model._meta,
            "action_name": action_name,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(request, template_name, context)


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


@admin.register(PublicToolLoan)
class PublicToolLoanAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = (
        "id",
        "makerspace",
        "status",
        "request",
        "requester",
        "target_label",
        "source",
        "checked_out_at",
    )
    list_filter = ("makerspace", "status", "source")
    search_fields = (
        "requester__username",
        "requester__email",
        "request__requester_username",
        "target_label",
    )
    readonly_fields = (
        "makerspace",
        "qr_code",
        "request",
        "requester",
        "target_type",
        "target_id",
        "target_label",
        "asset_ids",
        "qr_ids",
        "status",
        "source",
        "checked_out_at",
        "due_at",
        "returned_at",
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReturnEvent)
class ReturnEventAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("id", "makerspace", "request", "box", "actor", "created_at")
    list_filter = ("makerspace", "created_at")
    search_fields = (
        "request__requester_username",
        "request__requester__username",
        "request__requester__email",
        "actor__username",
        "actor__email",
        "box__label",
        "box__code",
    )
    readonly_fields = (
        "request",
        "makerspace",
        "box",
        "evidence",
        "remark",
        "actor",
        "created_at",
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RequesterAccountability)
class RequesterAccountabilityAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = (
        "id",
        "makerspace",
        "requester",
        "request",
        "issue_type",
        "quantity",
        "created_at",
    )
    list_filter = ("makerspace", "issue_type", "created_at")
    search_fields = (
        "requester__username",
        "requester__email",
        "request__requester_username",
        "request_item__product__name",
        "description",
    )
    readonly_fields = (
        "requester",
        "request",
        "request_item",
        "makerspace",
        "issue_type",
        "description",
        "evidence_photo",
        "quantity",
        "created_by",
        "created_at",
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HardwareRequestItemAsset)
class HardwareRequestItemAssetAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = (
        "id",
        "request_item",
        "asset",
        "asset_makerspace",
        "outcome",
        "issued_at",
        "returned_at",
    )
    list_filter = ("asset__makerspace", "outcome")
    search_fields = (
        "request_item__request__requester_username",
        "request_item__request__requester__username",
        "request_item__product__name",
        "asset__asset_tag",
        "asset__serial_number",
    )
    readonly_fields = (
        "request_item",
        "asset",
        "outcome",
        "issued_at",
        "returned_at",
        "return_event",
    )
    fields = readonly_fields

    @admin.display(description="Makerspace", ordering="asset__makerspace")
    def asset_makerspace(self, obj):
        return obj.asset.makerspace if obj.asset_id else "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
