from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.makerspaces.guards import require_module
from apps.printing.models import PrintPrinter
from apps.printing.permissions import CanManagePrinting
from apps.printing.serializers import PrintPrinterSerializer
from apps.printing.views_common import ERROR_RESPONSES, _int_query_param


class ManagedPrinterMixin:
    permission_classes = [CanManagePrinting]
    action = "printer_admin"

    def scope_queryset(self, qs, field="makerspace_id"):
        qs = rbac.scope_by_action(
            self.request.user,
            rbac.Action.MANAGE_PRINTING,
            qs,
            field,
        )
        makerspace_id = _int_query_param(self.request, "makerspace")
        if makerspace_id is not None:
            require_module(makerspace_id, "printing")
            qs = qs.filter(makerspace_id=makerspace_id)
        return qs

    def assert_can_manage_makerspace(self, makerspace_id):
        require_module(makerspace_id, "printing")
        if not rbac.can(self.request.user, rbac.Action.MANAGE_PRINTING, makerspace_id):
            raise ValidationError({"makerspace": "You cannot manage printing here."})


@extend_schema(tags=["Printing"], summary="List or create managed 3D printers")
class ManagedPrinterListCreateView(ManagedPrinterMixin, generics.ListCreateAPIView):
    serializer_class = PrintPrinterSerializer

    def get_queryset(self):
        return self.scope_queryset(
            PrintPrinter.objects.prefetch_related("filament_spools", "print_requests")
        )

    def perform_create(self, serializer):
        makerspace_id = serializer.validated_data["makerspace_id"]
        self.assert_can_manage_makerspace(makerspace_id)
        serializer.save()

    @extend_schema(
        parameters=[OpenApiParameter("makerspace", int, OpenApiParameter.QUERY)],
        responses={200: PrintPrinterSerializer(many=True), **ERROR_RESPONSES},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=PrintPrinterSerializer,
        responses={201: PrintPrinterSerializer, **ERROR_RESPONSES},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["Printing"], summary="Retrieve or update managed 3D printer")
class ManagedPrinterDetailView(ManagedPrinterMixin, generics.RetrieveUpdateAPIView):
    serializer_class = PrintPrinterSerializer

    def get_queryset(self):
        return self.scope_queryset(
            PrintPrinter.objects.prefetch_related("filament_spools", "print_requests")
        )

    def perform_update(self, serializer):
        makerspace_id = serializer.validated_data.get(
            "makerspace_id", serializer.instance.makerspace_id
        )
        self.assert_can_manage_makerspace(makerspace_id)
        serializer.save()

    @extend_schema(responses={200: PrintPrinterSerializer, **ERROR_RESPONSES})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=PrintPrinterSerializer,
        responses={200: PrintPrinterSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
