from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.admin_api.serializers_warranty import WarrantySerializer, WarrantyUpsertSerializer
from apps.admin_api.views_warranty_report import MakerspaceWarrantyReportView
from apps.admin_api.warranty_access import resolve_asset_host, resolve_printer_host
from apps.audit import services as audit
from apps.makerspaces.guards import require_module
from apps.warranty.models import Warranty


class AssetWarrantyView(APIView):
    permission_classes = [IsActiveStaff]

    def _asset(self, request, pk):
        asset = resolve_asset_host(request.user, pk)
        require_action(request.user, rbac.Action.EDIT_INVENTORY, asset.makerspace_id)
        require_module(asset.makerspace_id, "staff_admin")
        return asset

    @extend_schema(
        tags=["Admin warranty"],
        summary="Retrieve warranty details for an inventory asset",
        responses={200: WarrantySerializer},
    )
    def get(self, request, pk, *args, **kwargs):
        asset = self._asset(request, pk)
        warranty = _asset_warranty(asset)
        if warranty is None:
            return Response(None)
        return Response(WarrantySerializer(warranty).data)

    @extend_schema(
        tags=["Admin warranty"],
        summary="Create or update warranty details for an inventory asset",
        request=WarrantyUpsertSerializer,
        responses={
            200: WarrantySerializer,
            400: OpenApiResponse(description="Invalid warranty details."),
        },
    )
    def put(self, request, pk, *args, **kwargs):
        asset = self._asset(request, pk)
        serializer = WarrantyUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        warranty = serializer.save(asset=asset)
        audit.record(
            request.user,
            "warranty.created" if serializer.created else "warranty.updated",
            makerspace=asset.makerspace,
            target=warranty,
        )
        return Response(WarrantySerializer(_reload_warranty(warranty)).data)


class PrinterWarrantyView(APIView):
    permission_classes = [IsActiveStaff]

    def _printer(self, request, pk):
        printer = resolve_printer_host(request.user, pk)
        require_action(request.user, rbac.Action.MANAGE_PRINTING, printer.makerspace_id)
        require_module(printer.makerspace_id, "printing")
        return printer

    @extend_schema(
        tags=["Admin warranty"],
        summary="Retrieve warranty details for a 3D printer",
        responses={200: WarrantySerializer},
    )
    def get(self, request, pk, *args, **kwargs):
        printer = self._printer(request, pk)
        warranty = _printer_warranty(printer)
        if warranty is None:
            return Response(None)
        return Response(WarrantySerializer(warranty).data)

    @extend_schema(
        tags=["Admin warranty"],
        summary="Create or update warranty details for a 3D printer",
        request=WarrantyUpsertSerializer,
        responses={
            200: WarrantySerializer,
            400: OpenApiResponse(description="Invalid warranty details."),
        },
    )
    def put(self, request, pk, *args, **kwargs):
        printer = self._printer(request, pk)
        serializer = WarrantyUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        warranty = serializer.save(printer=printer)
        audit.record(
            request.user,
            "warranty.created" if serializer.created else "warranty.updated",
            makerspace=printer.makerspace,
            target=warranty,
        )
        return Response(WarrantySerializer(_reload_warranty(warranty)).data)


def _asset_warranty(asset):
    return (
        Warranty.objects.select_related("asset", "printer")
        .prefetch_related("documents")
        .filter(asset=asset)
        .first()
    )


def _printer_warranty(printer):
    return (
        Warranty.objects.select_related("asset", "printer")
        .prefetch_related("documents")
        .filter(printer=printer)
        .first()
    )


def _reload_warranty(warranty):
    return (
        Warranty.objects.select_related("asset", "printer")
        .prefetch_related("documents")
        .get(pk=warranty.pk)
    )



__all__ = ["AssetWarrantyView", "PrinterWarrantyView", "MakerspaceWarrantyReportView"]

