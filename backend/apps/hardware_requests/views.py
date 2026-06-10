from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.checkin import client as checkin
from apps.hardware_requests import workflow
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.permissions import (
    CanAssignBox,
    CanIssueRequest,
    CanReviewRequest,
    CanViewHandoverQueue,
)
from apps.hardware_requests.serializers import (
    AdminRequestSerializer,
    AssignBoxSerializer,
    CheckinVerifyRequestSerializer,
    CheckinVerifyResponseSerializer,
    IssueRequestSerializer,
    PublicRequestStatusSerializer,
    RejectRequestSerializer,
    RequestSubmitResponseSerializer,
    RequestSubmitSerializer,
)
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace


ERROR_400 = OpenApiResponse(ErrorSerializer, description="Invalid request.")
ERROR_403 = OpenApiResponse(ErrorSerializer, description="Permission denied.")
ERROR_404 = OpenApiResponse(ErrorSerializer, description="Not found.")
ERROR_409 = OpenApiResponse(ErrorSerializer, description="Workflow conflict.")
ERROR_503 = OpenApiResponse(ErrorSerializer, description="Check-in unavailable.")

PUBLIC_ERROR_RESPONSES = {
    400: ERROR_400,
    403: ERROR_403,
    404: ERROR_404,
    503: ERROR_503,
}
ADMIN_LIST_ERROR_RESPONSES = {
    403: ERROR_403,
    404: ERROR_404,
}
ACTION_ERROR_RESPONSES = {
    400: ERROR_400,
    403: ERROR_403,
    404: ERROR_404,
    409: ERROR_409,
}


def _request_queryset():
    return HardwareRequest.objects.select_related(
        "makerspace",
        "requester",
        "accepted_by",
        "assigned_box",
        "issued_by",
        "issue_evidence",
    ).prefetch_related("items__product")


class CheckinVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkin_verify"

    @extend_schema(
        request=CheckinVerifyRequestSerializer,
        responses={200: CheckinVerifyResponseSerializer, **PUBLIC_ERROR_RESPONSES},
    )
    def post(self, request, makerspace_slug, *args, **kwargs):
        makerspace = get_object_or_404(Makerspace, slug=makerspace_slug)
        serializer = CheckinVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = checkin.verify(
            makerspace,
            serializer.validated_data["identifier"],
        )
        return Response(CheckinVerifyResponseSerializer(result).data)


class RequestSubmitView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "request_submit"

    @extend_schema(
        request=RequestSubmitSerializer,
        responses={201: RequestSubmitResponseSerializer, **PUBLIC_ERROR_RESPONSES},
    )
    def post(self, request, makerspace_slug, *args, **kwargs):
        makerspace = get_object_or_404(Makerspace, slug=makerspace_slug)
        serializer = RequestSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        product_ids = [item["product_id"] for item in data["items"]]
        products = {
            product.pk: product
            for product in InventoryProduct.objects.filter(
                pk__in=product_ids,
                makerspace=makerspace,
                is_public=True,
                is_archived=False,
            )
        }
        if len(products) != len(product_ids):
            raise ValidationError(
                {"items": "One or more products are unavailable for request."}
            )

        items = [
            {
                "product": products[item["product_id"]],
                "quantity": item["quantity"],
            }
            for item in data["items"]
        ]
        hardware_request = workflow.submit_request(
            makerspace,
            data["identifier"],
            items,
            data["requested_for"],
        )
        return Response(
            RequestSubmitResponseSerializer(hardware_request).data,
            status=status.HTTP_201_CREATED,
        )


class RequestStatusView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "request_status"
    serializer_class = PublicRequestStatusSerializer
    lookup_field = "public_token"
    queryset = _request_queryset()

    @extend_schema(
        responses={200: PublicRequestStatusSerializer, 404: ERROR_404},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PendingRequestsView(generics.ListAPIView):
    permission_classes = [CanReviewRequest]
    serializer_class = AdminRequestSerializer

    def get_queryset(self):
        makerspace_id = self.kwargs["makerspace_id"]
        get_object_or_404(Makerspace, pk=makerspace_id)
        if not rbac.can(
            self.request.user,
            rbac.Action.ACCEPT_REQUEST,
            makerspace_id,
        ):
            raise PermissionDenied()

        return (
            _request_queryset()
            .filter(
                makerspace_id=makerspace_id,
                status=HardwareRequest.Status.PENDING_APPROVAL,
            )
            .order_by("-created_at")
        )

    @extend_schema(
        responses={200: AdminRequestSerializer(many=True), **ADMIN_LIST_ERROR_RESPONSES},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AcceptedRequestsView(generics.ListAPIView):
    permission_classes = [CanViewHandoverQueue]
    serializer_class = AdminRequestSerializer

    def get_queryset(self):
        makerspace_id = self.kwargs["makerspace_id"]
        get_object_or_404(Makerspace, pk=makerspace_id)
        if not rbac.can(
            self.request.user,
            rbac.Action.ISSUE_REQUEST,
            makerspace_id,
        ):
            raise PermissionDenied()

        return (
            _request_queryset()
            .filter(
                makerspace_id=makerspace_id,
                status=HardwareRequest.Status.ACCEPTED,
            )
            .order_by("-created_at")
        )

    @extend_schema(
        responses={200: AdminRequestSerializer(many=True), **ADMIN_LIST_ERROR_RESPONSES},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ActiveLoansView(generics.ListAPIView):
    permission_classes = [CanViewHandoverQueue]
    serializer_class = AdminRequestSerializer

    def get_queryset(self):
        makerspace_id = self.kwargs["makerspace_id"]
        get_object_or_404(Makerspace, pk=makerspace_id)
        if not rbac.can(
            self.request.user,
            rbac.Action.ISSUE_REQUEST,
            makerspace_id,
        ):
            raise PermissionDenied()

        return (
            _request_queryset()
            .filter(
                makerspace_id=makerspace_id,
                status__in=[
                    HardwareRequest.Status.ISSUED,
                    HardwareRequest.Status.PARTIALLY_RETURNED,
                ],
            )
            .order_by("-issued_at", "-created_at")
        )

    @extend_schema(
        responses={200: AdminRequestSerializer(many=True), **ADMIN_LIST_ERROR_RESPONSES},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AcceptRequestView(APIView):
    permission_classes = [CanReviewRequest]

    @extend_schema(
        request=None,
        responses={200: AdminRequestSerializer, **ACTION_ERROR_RESPONSES},
    )
    def post(self, request, pk, *args, **kwargs):
        scoped = rbac.scope_by_makerspace(
            request.user,
            _request_queryset(),
        )
        hardware_request = get_object_or_404(scoped, pk=pk)
        if not rbac.can(
            request.user,
            rbac.Action.ACCEPT_REQUEST,
            hardware_request.makerspace_id,
        ):
            raise PermissionDenied()

        updated = workflow.accept_request(request.user, hardware_request)
        return Response(AdminRequestSerializer(updated).data)


class RejectRequestView(APIView):
    permission_classes = [CanReviewRequest]

    @extend_schema(
        request=RejectRequestSerializer,
        responses={200: AdminRequestSerializer, **ACTION_ERROR_RESPONSES},
    )
    def post(self, request, pk, *args, **kwargs):
        scoped = rbac.scope_by_makerspace(
            request.user,
            _request_queryset(),
        )
        hardware_request = get_object_or_404(scoped, pk=pk)
        if not rbac.can(
            request.user,
            rbac.Action.REJECT_REQUEST,
            hardware_request.makerspace_id,
        ):
            raise PermissionDenied()

        serializer = RejectRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = workflow.reject_request(
            request.user,
            hardware_request,
            serializer.validated_data["reason"],
        )
        return Response(AdminRequestSerializer(updated).data)


class AssignBoxView(APIView):
    permission_classes = [CanAssignBox]

    @extend_schema(
        request=AssignBoxSerializer,
        responses={200: AdminRequestSerializer, **ACTION_ERROR_RESPONSES},
    )
    def post(self, request, pk, *args, **kwargs):
        scoped = rbac.scope_by_makerspace(
            request.user,
            _request_queryset(),
        )
        hardware_request = get_object_or_404(scoped, pk=pk)
        if not rbac.can(
            request.user,
            rbac.Action.ASSIGN_BOX,
            hardware_request.makerspace_id,
        ):
            raise PermissionDenied()

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
        scoped = rbac.scope_by_makerspace(
            request.user,
            _request_queryset(),
        )
        hardware_request = get_object_or_404(scoped, pk=pk)
        if not rbac.can(
            request.user,
            rbac.Action.ISSUE_REQUEST,
            hardware_request.makerspace_id,
        ):
            raise PermissionDenied()

        serializer = IssueRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = workflow.issue_request(
            request.user,
            hardware_request,
            serializer.validated_data["evidence_id"],
            serializer.validated_data["remark"],
        )
        return Response(AdminRequestSerializer(updated).data)
