from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.admin_api.serializers_email_templates import (
    EmailLayoutSerializer,
    EmailPreviewRequestSerializer,
    EmailRenderedSerializer,
    EmailTemplateRowSerializer,
    EmailTemplateWriteSerializer,
)
from apps.audit import services as audit
from apps.integrations import email_registry
from apps.integrations.email_models import EmailLayout, EmailTemplate
from apps.integrations.email_render import (
    DEFAULT_LAYOUT_HTML,
    render_email_preview,
    render_email_template,
)
from apps.makerspaces.models import Makerspace

_ACTION_BY_NAME = {
    "EDIT_INVENTORY": rbac.Action.EDIT_INVENTORY,
    "MANAGE_PRINTING": rbac.Action.MANAGE_PRINTING,
}
_TAGS = ["Email templates"]
_ERROR_RESPONSES = {
    403: OpenApiResponse(description="Permission denied."),
    404: OpenApiResponse(description="Not found."),
}


def _resolve_makerspace_or_404(user, makerspace_id):
    try:
        makerspace = Makerspace.objects.get(pk=makerspace_id)
    except Makerspace.DoesNotExist:
        raise NotFound()
    if not (
        rbac.can(user, rbac.Action.EDIT_INVENTORY, makerspace.id)
        or rbac.can(user, rbac.Action.MANAGE_PRINTING, makerspace.id)
        or rbac.can(user, rbac.Action.MANAGE_MAKERSPACE, makerspace.id)
    ):
        raise NotFound()
    return makerspace


def _entry_action(entry):
    return _ACTION_BY_NAME[entry["action"]]


def _template_row(key, entry, override=None):
    return {
        "key": key,
        "family": entry["family"],
        "audience": entry["audience"],
        "label": entry["label"],
        "variables": entry["variables"],
        "subject": override.subject if override else entry["default_subject"],
        "text_body": override.text_body if override else entry["default_text"],
        "html_body": override.html_body if override else entry["default_html"],
        "is_active": override.is_active if override else True,
        "is_customized": bool(override),
    }


def _layout_row(layout=None):
    if layout is None:
        return {"html": DEFAULT_LAYOUT_HTML, "is_active": True, "is_default": True}
    return {"html": layout.html, "is_active": layout.is_active, "is_default": False}


@extend_schema(tags=_TAGS, summary="List editable email templates")
class EmailTemplateListView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=_TAGS,
        responses={200: EmailTemplateRowSerializer(many=True), **_ERROR_RESPONSES},
    )
    def get(self, request, makerspace_id, *args, **kwargs):
        makerspace = _resolve_makerspace_or_404(request.user, makerspace_id)
        included = [
            key
            for key, entry in email_registry.EMAIL_TEMPLATES.items()
            if rbac.can(request.user, _entry_action(entry), makerspace.id)
        ]
        overrides = {
            item.key: item
            for item in EmailTemplate.objects.filter(makerspace=makerspace, key__in=included)
        }
        rows = [
            _template_row(key, email_registry.EMAIL_TEMPLATES[key], overrides.get(key))
            for key in included
        ]
        rows.sort(key=lambda row: (row["family"], row["key"]))
        return Response(EmailTemplateRowSerializer(rows, many=True).data)


@extend_schema(tags=_TAGS, summary="Retrieve, update, or reset an email template")
class EmailTemplateDetailView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "put", "delete", "head", "options"]

    def _context(self, user, makerspace_id, key):
        entry = email_registry.EMAIL_TEMPLATES.get(key)
        if entry is None:
            raise NotFound()
        makerspace = _resolve_makerspace_or_404(user, makerspace_id)
        action = _entry_action(entry)
        return makerspace, entry, action

    @extend_schema(
        tags=_TAGS,
        responses={200: EmailTemplateRowSerializer, **_ERROR_RESPONSES},
    )
    def get(self, request, makerspace_id, key, *args, **kwargs):
        makerspace, entry, action = self._context(request.user, makerspace_id, key)
        require_action(request.user, action, makerspace.id)
        override = EmailTemplate.objects.filter(makerspace=makerspace, key=key).first()
        return Response(EmailTemplateRowSerializer(_template_row(key, entry, override)).data)

    @extend_schema(
        tags=_TAGS,
        request=EmailTemplateWriteSerializer,
        responses={
            200: EmailTemplateRowSerializer,
            400: OpenApiResponse(description="Invalid email template."),
            **_ERROR_RESPONSES,
        },
    )
    def put(self, request, makerspace_id, key, *args, **kwargs):
        makerspace, entry, action = self._context(request.user, makerspace_id, key)
        require_action(request.user, action, makerspace.id)
        serializer = EmailTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        override, _created = EmailTemplate.objects.update_or_create(
            makerspace=makerspace,
            key=key,
            defaults=serializer.validated_data,
        )
        audit.record(
            request.user,
            "email_template.updated",
            makerspace=makerspace,
            target=makerspace,
            meta={"key": key},
        )
        return Response(EmailTemplateRowSerializer(_template_row(key, entry, override)).data)

    @extend_schema(tags=_TAGS, request=None, responses={204: None, **_ERROR_RESPONSES})
    def delete(self, request, makerspace_id, key, *args, **kwargs):
        makerspace, _entry, action = self._context(request.user, makerspace_id, key)
        require_action(request.user, action, makerspace.id)
        EmailTemplate.objects.filter(makerspace=makerspace, key=key).delete()
        audit.record(
            request.user,
            "email_template.reset",
            makerspace=makerspace,
            target=makerspace,
            meta={"key": key},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=_TAGS, summary="Retrieve or update the email base layout")
class EmailLayoutView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "put", "head", "options"]

    def _makerspace(self, request, makerspace_id):
        makerspace = get_object_or_404(Makerspace, pk=makerspace_id)
        if not rbac.can(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace.id):
            raise NotFound()
        require_action(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace.id)
        return makerspace

    @extend_schema(
        tags=_TAGS,
        responses={200: EmailLayoutSerializer, **_ERROR_RESPONSES},
    )
    def get(self, request, makerspace_id, *args, **kwargs):
        makerspace = self._makerspace(request, makerspace_id)
        layout = EmailLayout.objects.filter(makerspace=makerspace).first()
        return Response(EmailLayoutSerializer(_layout_row(layout)).data)

    @extend_schema(
        tags=_TAGS,
        request=EmailLayoutSerializer,
        responses={
            200: EmailLayoutSerializer,
            400: OpenApiResponse(description="Invalid email layout."),
            **_ERROR_RESPONSES,
        },
    )
    def put(self, request, makerspace_id, *args, **kwargs):
        makerspace = self._makerspace(request, makerspace_id)
        serializer = EmailLayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        layout, _created = EmailLayout.objects.update_or_create(
            makerspace=makerspace,
            defaults={
                "html": serializer.validated_data["html"],
                "is_active": serializer.validated_data["is_active"],
            },
        )
        audit.record(
            request.user,
            "email_layout.updated",
            makerspace=makerspace,
            target=makerspace,
        )
        return Response(EmailLayoutSerializer(_layout_row(layout)).data)


@extend_schema(tags=_TAGS, summary="Preview an email template")
class EmailTemplatePreviewView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=_TAGS,
        request=EmailPreviewRequestSerializer,
        responses={200: EmailRenderedSerializer, **_ERROR_RESPONSES},
    )
    def post(self, request, makerspace_id, key, *args, **kwargs):
        entry = email_registry.EMAIL_TEMPLATES.get(key)
        if entry is None:
            raise NotFound()
        makerspace = _resolve_makerspace_or_404(request.user, makerspace_id)
        require_action(request.user, _entry_action(entry), makerspace.id)
        draft = EmailPreviewRequestSerializer(data=request.data)
        draft.is_valid(raise_exception=True)
        variables = {item["name"]: item["sample"] for item in entry["variables"]}
        # Render the unsaved editor draft when fields are posted; otherwise the
        # stored/default template. `partial` keys (omitted) fall back to defaults.
        if draft.validated_data:
            rendered = render_email_preview(
                makerspace,
                key,
                variables,
                subject=draft.validated_data.get("subject"),
                text_body=draft.validated_data.get("text_body"),
                html_body=draft.validated_data.get("html_body"),
            )
        else:
            rendered = render_email_template(makerspace, key, variables)
        return Response(EmailRenderedSerializer(rendered).data)
