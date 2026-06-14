from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics

from apps.printing.models import FilamentSpool
from apps.printing.serializers import FilamentSpoolSerializer
from apps.printing.views_common import ERROR_RESPONSES, _int_query_param
from apps.printing.views_printers import ManagedPrinterMixin


@extend_schema(tags=["Printing"], summary="List or create managed filament spools")
class ManagedFilamentSpoolListCreateView(
    ManagedPrinterMixin, generics.ListCreateAPIView
):
    serializer_class = FilamentSpoolSerializer

    def get_queryset(self):
        qs = self.scope_queryset(
            FilamentSpool.objects.select_related("printer", "makerspace")
        )
        printer_id = _int_query_param(self.request, "printer")
        if printer_id is not None:
            qs = qs.filter(printer_id=printer_id)
        return qs

    def perform_create(self, serializer):
        makerspace_id = serializer.validated_data["makerspace_id"]
        self.assert_can_manage_makerspace(makerspace_id)
        serializer.save()

    @extend_schema(
        parameters=[
            OpenApiParameter("makerspace", int, OpenApiParameter.QUERY),
            OpenApiParameter("printer", int, OpenApiParameter.QUERY),
        ],
        responses={200: FilamentSpoolSerializer(many=True), **ERROR_RESPONSES},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=FilamentSpoolSerializer,
        responses={201: FilamentSpoolSerializer, **ERROR_RESPONSES},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["Printing"], summary="Retrieve or update managed filament spool")
class ManagedFilamentSpoolDetailView(ManagedPrinterMixin, generics.RetrieveUpdateAPIView):
    serializer_class = FilamentSpoolSerializer

    def get_queryset(self):
        return self.scope_queryset(
            FilamentSpool.objects.select_related("printer", "makerspace")
        )

    def perform_update(self, serializer):
        makerspace_id = serializer.validated_data.get(
            "makerspace_id", serializer.instance.makerspace_id
        )
        self.assert_can_manage_makerspace(makerspace_id)
        serializer.save()

    @extend_schema(responses={200: FilamentSpoolSerializer, **ERROR_RESPONSES})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=FilamentSpoolSerializer,
        responses={200: FilamentSpoolSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
