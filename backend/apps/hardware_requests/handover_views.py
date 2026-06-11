from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.hardware_requests import workflow
from apps.hardware_requests.permissions import (
    CanAssignBox,
    CanIssueRequest,
    CanReturnRequest,
)
from apps.hardware_requests.serializers import (
    AdminRequestSerializer,
    AssignBoxSerializer,
    IssueRequestSerializer,
    ReturnRequestSerializer,
)
from apps.hardware_requests.view_helpers import (
    ACTION_ERROR_RESPONSES,
    ERROR_503,
    request_queryset,
)


class AssignBoxView(APIView):
    permission_classes = [CanAssignBox]

    @extend_schema(
        request=AssignBoxSerializer,
        responses={200: AdminRequestSerializer, **ACTION_ERROR_RESPONSES},
    )
    def post(self, request, pk, *args, **kwargs):
        hardware_request = _scoped_action_request(
            request.user,
            pk,
            rbac.Action.ASSIGN_BOX,
        )
        serializer = AssignBoxSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = workflow.assign_box(
            request.user,
            hardware_request,
            serializer.validated_data["box_code"],
        )
        return Response(AdminRequestSerializer(updated).data)


class IssueRequestView(APIView):
    permission_classes = [CanIssueRequest]

    @extend_schema(
        request=IssueRequestSerializer,
        responses={200: AdminRequestSerializer, **ACTION_ERROR_RESPONSES, 503: ERROR_503},
    )
    def post(self, request, pk, *args, **kwargs):
        hardware_request = _scoped_action_request(
            request.user,
            pk,
            rbac.Action.ISSUE_REQUEST,
        )
        serializer = IssueRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = workflow.issue_request(
            request.user,
            hardware_request,
            serializer.validated_data["evidence_id"],
            serializer.validated_data["remark"],
        )
        return Response(AdminRequestSerializer(updated).data)


class ReturnRequestView(APIView):
    permission_classes = [CanReturnRequest]

    @extend_schema(
        request=ReturnRequestSerializer,
        responses={200: AdminRequestSerializer, **ACTION_ERROR_RESPONSES, 503: ERROR_503},
    )
    def post(self, request, pk, *args, **kwargs):
        hardware_request = _scoped_action_request(
            request.user,
            pk,
            rbac.Action.RETURN_REQUEST,
        )
        serializer = ReturnRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = workflow.return_items(
            request.user,
            hardware_request,
            serializer.validated_data["evidence_id"],
            serializer.validated_data["remark"],
            serializer.validated_data["box_code"],
            serializer.validated_data["resolutions"],
        )
        return Response(AdminRequestSerializer(updated).data)


def _scoped_action_request(user, pk, action):
    scoped = rbac.scope_by_makerspace(user, request_queryset())
    hardware_request = get_object_or_404(scoped, pk=pk)
    if not rbac.can(user, action, hardware_request.makerspace_id):
        raise PermissionDenied()
    return hardware_request
