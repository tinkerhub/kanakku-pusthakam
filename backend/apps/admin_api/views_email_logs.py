from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.integrations.dispatch import _enqueue
from apps.integrations.models import EmailLog
from apps.makerspaces.models import Makerspace

# Under at-most-once delivery (CELERY_TASK_ACKS_LATE=False) a worker that dies mid-send
# leaves the row PENDING with no further progress. A PENDING row whose updated_at hasn't
# advanced past this window is treated as stalled and becomes retryable (alongside FAILED),
# so a stranded email is recoverable instead of polling forever with no action.
STALE_PENDING_AFTER = timedelta(minutes=10)


def _can_retry(log):
    if not (log.text_body or log.html_body):
        return False
    if log.status == EmailLog.Status.FAILED:
        return True
    if log.status == EmailLog.Status.PENDING:
        return log.updated_at < timezone.now() - STALE_PENDING_AFTER
    return False


_EMAIL_LOG_FIELDS = (
    "id",
    "to_email",
    "subject",
    "stream",
    "event",
    "audience",
    "status",
    "error",
    "attempts",
    "created_at",
    "sent_at",
)


class EmailLogPagination(PageNumberPagination):
    page_size = 24


class EmailLogSerializer(serializers.ModelSerializer):
    can_retry = serializers.SerializerMethodField()

    class Meta:
        model = EmailLog
        fields = (*_EMAIL_LOG_FIELDS, "can_retry")
        read_only_fields = _EMAIL_LOG_FIELDS

    def get_can_retry(self, obj) -> bool:
        return _can_retry(obj)


@extend_schema(
    tags=["Email logs"],
    summary="List makerspace email delivery logs",
    parameters=[OpenApiParameter("status", str, OpenApiParameter.QUERY)],
    responses={
        200: EmailLogSerializer(many=True),
        400: OpenApiResponse(description="Invalid status filter."),
        404: OpenApiResponse(description="Makerspace not found."),
    },
)
class EmailLogListView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "head", "options"]
    pagination_class = EmailLogPagination

    def get(self, request, makerspace_id, *args, **kwargs):
        makerspace = get_object_or_404(
            rbac.scope_by_action(
                request.user,
                rbac.Action.MANAGE_MAKERSPACE,
                Makerspace.objects.filter(archived_at__isnull=True),
                field="id",
            ),
            pk=makerspace_id,
        )
        queryset = EmailLog.objects.filter(makerspace=makerspace).order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            valid_statuses = {choice for choice, _ in EmailLog.Status.choices}
            if status_filter not in valid_statuses:
                return Response(
                    {"status": "Invalid status filter."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(status=status_filter)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = EmailLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    tags=["Email logs"],
    summary="Retry a failed makerspace email",
    request=None,
    responses={
        200: EmailLogSerializer,
        400: OpenApiResponse(description="Email log cannot be retried."),
        404: OpenApiResponse(description="Email log not found."),
    },
)
class EmailLogRetryView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["post", "options"]

    def post(self, request, makerspace_id, pk, *args, **kwargs):
        queryset = rbac.scope_by_action(
            request.user,
            rbac.Action.MANAGE_MAKERSPACE,
            EmailLog.objects.filter(makerspace__archived_at__isnull=True),
            field="makerspace_id",
        )
        # The makerspace_id path segment gives the origin-scope guard tenant context
        # (so tenant-domain admins aren't 403'd); also pins the log to that makerspace.
        log = get_object_or_404(queryset, pk=pk, makerspace_id=makerspace_id)
        if not log.text_body and not log.html_body:
            return Response(
                {"detail": "This email cannot be retried (no stored content)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not _can_retry(log):
            # FAILED, or a PENDING row stalled past STALE_PENDING_AFTER (a crashed
            # at-most-once delivery). A fresh PENDING / already-SENT row is not retryable.
            return Response(
                {"detail": "Only failed or stalled emails can be retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log.status = EmailLog.Status.PENDING
        log.error = ""
        log.save(update_fields=["status", "error", "updated_at"])
        audit.record(
            request.user,
            "email.retried",
            makerspace=log.makerspace,
            target=log,
            meta={"to_email": log.to_email, "event": log.event, "stream": log.stream},
        )
        transaction.on_commit(lambda: _enqueue(log.pk))
        return Response(EmailLogSerializer(log).data)
