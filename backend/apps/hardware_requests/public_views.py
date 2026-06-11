from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.checkin import client as checkin
from apps.hardware_requests import workflow
from apps.hardware_requests.serializers import (
    CheckinVerifyRequestSerializer,
    CheckinVerifyResponseSerializer,
    PublicRequestStatusSerializer,
    RequestSubmitResponseSerializer,
    RequestSubmitSerializer,
)
from apps.hardware_requests.view_helpers import ERROR_404, PUBLIC_ERROR_RESPONSES
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace


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

        result = checkin.verify(makerspace, serializer.validated_data["identifier"])
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
        products = _requestable_products(product_ids, makerspace)
        if len(products) != len(product_ids):
            raise ValidationError(
                {"items": "One or more products are unavailable for request."}
            )

        hardware_request = workflow.submit_request(
            makerspace,
            data["identifier"],
            [
                {
                    "product": products[item["product_id"]],
                    "quantity": item["quantity"],
                }
                for item in data["items"]
            ],
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

    def get_queryset(self):
        from apps.hardware_requests.view_helpers import request_queryset

        return request_queryset()

    @extend_schema(responses={200: PublicRequestStatusSerializer, 404: ERROR_404})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


def _requestable_products(product_ids, makerspace):
    return {
        product.pk: product
        for product in InventoryProduct.objects.filter(
            pk__in=product_ids,
            makerspace=makerspace,
            is_public=True,
            is_archived=False,
        )
    }
