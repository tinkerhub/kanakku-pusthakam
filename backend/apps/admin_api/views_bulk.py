import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api import bulk_import
from apps.admin_api.models import BulkImportJob
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.admin_api.serializers_bulk import (
    BulkImportJobCreateSerializer,
    BulkImportJobSerializer,
    BulkImportPreviewSerializer,
)
from apps.admin_api.tasks import process_bulk_import_job
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace
from apps.openapi import BULK_IMPORT_ROWS_EXAMPLE

logger = logging.getLogger(__name__)


def _enqueue_bulk_import_job(job_id):
    # Fail-safe: a broker outage must not 500 the request post-commit or leave the job
    # stuck PENDING. Mark it FAILED so staff see a recoverable state and can retry
    # (mirrors the email dispatch fail-safe).
    try:
        process_bulk_import_job.delay(job_id)
    except Exception:
        logger.exception("Failed to enqueue bulk import job %s", job_id)
        BulkImportJob.objects.filter(
            pk=job_id, status=BulkImportJob.Status.PENDING
        ).update(
            status=BulkImportJob.Status.FAILED,
            error="Could not queue the import job. Please retry.",
            completed_at=timezone.now(),
        )


def _rows_from_upload(uploaded_file):
    """Parse an uploaded import file, mapping bad-input parse errors to 400.

    rows_from_upload raises ValueError (incl. JSONDecodeError/UnicodeDecodeError,
    and normalized corrupt-XLSX errors) on malformed files; without this they'd
    surface as a 500 for what is really user input.
    """
    try:
        return bulk_import.rows_from_upload(uploaded_file)
    except ValueError as exc:
        raise ValidationError({"file": str(exc) or "Uploaded file could not be parsed."})


def _authorized_makerspace(request, makerspace_id):
    makerspace = get_object_or_404(Makerspace, pk=makerspace_id)
    require_module(makerspace, "bulk_import")
    require_action(request.user, rbac.Action.EDIT_INVENTORY, makerspace_id)
    return makerspace


class BulkImportPreviewView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Bulk import"],
        summary="Preview inventory bulk import",
        request=BulkImportPreviewSerializer,
        responses={200: OpenApiResponse(description="Import preview with row errors.")},
        examples=[BULK_IMPORT_ROWS_EXAMPLE],
    )
    def post(self, request, makerspace_id, *args, **kwargs):
        makerspace = _authorized_makerspace(request, makerspace_id)
        serializer = BulkImportPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data.get("rows")
        if rows is None:
            rows = _rows_from_upload(serializer.validated_data["file"])
        try:
            result = bulk_import.preview_import(
                makerspace,
                rows,
                serializer.validated_data.get("mapping") or {},
            )
        except IntegrityError:
            return Response(
                {"detail": "Import failed due to a data conflict; no changes were applied."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(result)


class BulkImportApplyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Bulk import"],
        summary="Apply inventory bulk import",
        request=BulkImportPreviewSerializer,
        responses={200: OpenApiResponse(description="Import application result.")},
        examples=[BULK_IMPORT_ROWS_EXAMPLE],
    )
    def post(self, request, makerspace_id, *args, **kwargs):
        makerspace = _authorized_makerspace(request, makerspace_id)
        serializer = BulkImportPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data.get("rows")
        if rows is None:
            rows = _rows_from_upload(serializer.validated_data["file"])
        try:
            result = bulk_import.apply_import(
                request.user,
                makerspace,
                rows,
                serializer.validated_data.get("mapping") or {},
            )
        except IntegrityError:
            return Response(
                {"detail": "Import failed due to a data conflict; no changes were applied."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(result, status=status.HTTP_200_OK)


class BulkImportJobListCreateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Bulk import"],
        summary="Create an async inventory bulk import job",
        request=BulkImportJobCreateSerializer,
        responses={201: BulkImportJobSerializer},
    )
    def post(self, request, makerspace_id, *args, **kwargs):
        makerspace = _authorized_makerspace(request, makerspace_id)
        serializer = BulkImportJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data.get("rows")
        if rows is None:
            rows = _rows_from_upload(serializer.validated_data["file"])
        with transaction.atomic():
            job = BulkImportJob.objects.create(
                makerspace=makerspace,
                actor=request.user,
                mode=serializer.validated_data["mode"],
                rows=rows,
                mapping=serializer.validated_data.get("mapping") or {},
            )
            transaction.on_commit(
                lambda job_id=job.id: _enqueue_bulk_import_job(job_id)
            )
        if settings.CELERY_TASK_ALWAYS_EAGER:
            _enqueue_bulk_import_job(job.id)
        job.refresh_from_db()
        return Response(BulkImportJobSerializer(job).data, status=status.HTTP_201_CREATED)


class BulkImportJobDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Bulk import"],
        summary="Get async inventory bulk import job status",
        responses={200: BulkImportJobSerializer},
    )
    def get(self, request, makerspace_id, job_id, *args, **kwargs):
        _authorized_makerspace(request, makerspace_id)
        job = get_object_or_404(
            BulkImportJob,
            pk=job_id,
            makerspace_id=makerspace_id,
        )
        return Response(BulkImportJobSerializer(job).data)
