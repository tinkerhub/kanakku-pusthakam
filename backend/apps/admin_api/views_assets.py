from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_inventory import InventoryAssetAdminSerializer
from apps.admin_api.views_inventory import InventoryPagination
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.makerspaces.guards import require_module


class InventoryAssetListView(generics.ListAPIView):
    serializer_class = InventoryAssetAdminSerializer
    permission_classes = [IsActiveStaff]
    pagination_class = InventoryPagination

    @extend_schema(
        tags=["Admin inventory"],
        summary="List individual assets for an inventory product",
        responses=InventoryAssetAdminSerializer(many=True),
    )
    def get(self, request, product_pk, *args, **kwargs):
        return super().get(request, product_pk, *args, **kwargs)

    def get_queryset(self):
        product = get_object_or_404(
            rbac.scope_by_action(
                self.request.user,
                rbac.Action.VIEW_INVENTORY,
                InventoryProduct.objects.all(),
            ),
            pk=self.kwargs["product_pk"],
        )
        require_module(product.makerspace_id, "staff_admin")
        return (
            InventoryAsset.objects.select_related("product", "box", "makerspace")
            .filter(product=product)
            .order_by("asset_tag", "id")
        )
