from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.admin_api.serializers_inventory import (
    InventoryProductAdminSerializer,
    InventoryQuantityAdjustmentSerializer,
)
from apps.audit import services as audit
from apps.inventory.models import InventoryProduct
from apps.makerspaces.guards import require_module
from apps.operations.models import InventoryAdjustment


@extend_schema(tags=["Admin inventory"], summary="List or create inventory products")
class InventoryListCreateView(generics.ListCreateAPIView):
    serializer_class = InventoryProductAdminSerializer
    permission_classes = [IsActiveStaff]

    def get_queryset(self):
        makerspace_id = self.kwargs["makerspace_id"]
        require_module(makerspace_id, "staff_admin")
        require_action(self.request.user, rbac.Action.VIEW_INVENTORY, makerspace_id)
        return InventoryProduct.objects.filter(makerspace_id=makerspace_id).order_by("name")

    def perform_create(self, serializer):
        makerspace_id = self.kwargs["makerspace_id"]
        require_module(makerspace_id, "staff_admin")
        require_action(self.request.user, rbac.Action.EDIT_INVENTORY, makerspace_id)
        _assert_box_in_makerspace(serializer.validated_data.get("box"), makerspace_id)
        _assert_category_in_makerspace(
            serializer.validated_data.get("category"), makerspace_id
        )
        instance = serializer.save(makerspace_id=makerspace_id)
        audit.record(
            self.request.user,
            "inventory.created",
            makerspace=instance.makerspace,
            target=instance,
        )


@extend_schema(tags=["Admin inventory"], summary="Retrieve or update inventory product")
class InventoryDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = InventoryProductAdminSerializer
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        action = (
            rbac.Action.EDIT_INVENTORY
            if self.request.method == "PATCH"
            else rbac.Action.VIEW_INVENTORY
        )
        return rbac.scope_by_action(self.request.user, action, InventoryProduct.objects.select_related("makerspace", "box"))

    def perform_update(self, serializer):
        _assert_box_in_makerspace(
            serializer.validated_data.get("box"), serializer.instance.makerspace_id
        )
        _assert_category_in_makerspace(
            serializer.validated_data.get("category"), serializer.instance.makerspace_id
        )
        instance = serializer.save()
        audit.record(
            self.request.user,
            "inventory.updated",
            makerspace=instance.makerspace,
            target=instance,
        )


class InventoryQuantityAdjustmentView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin inventory"],
        summary="Adjust inventory quantity buckets",
        request=InventoryQuantityAdjustmentSerializer,
        responses={200: InventoryProductAdminSerializer},
    )
    def post(self, request, pk, *args, **kwargs):
        product = get_object_or_404(
            rbac.scope_by_action(
                request.user,
                rbac.Action.VIEW_INVENTORY,
                InventoryProduct.objects.select_related("makerspace"),
            ),
            pk=pk,
        )
        require_module(product.makerspace_id, "staff_admin")
        require_action(request.user, rbac.Action.EDIT_INVENTORY, product.makerspace_id)
        serializer = InventoryQuantityAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            locked = InventoryProduct.objects.select_for_update().get(pk=product.pk)
            available = locked.available_quantity + data["delta_available"]
            damaged = locked.damaged_quantity + data["delta_damaged"]
            lost = locked.lost_quantity + data["delta_lost"]
            if available < 0 or damaged < 0 or lost < 0:
                raise ValidationError("Quantity adjustment cannot make a bucket negative.")
            locked.available_quantity = available
            locked.damaged_quantity = damaged
            locked.lost_quantity = lost
            locked.total_quantity = (
                locked.available_quantity
                + locked.reserved_quantity
                + locked.issued_quantity
                + locked.damaged_quantity
                + locked.lost_quantity
            )
            locked.save(
                update_fields=[
                    "available_quantity",
                    "damaged_quantity",
                    "lost_quantity",
                    "total_quantity",
                    "updated_at",
                ]
            )
            InventoryAdjustment.objects.create(
                makerspace=locked.makerspace,
                product=locked,
                delta_available=data["delta_available"],
                delta_damaged=data["delta_damaged"],
                delta_lost=data["delta_lost"],
                reason=data["reason"],
                created_by=request.user,
            )
            audit.record(
                request.user,
                "inventory.quantity_adjusted",
                makerspace=locked.makerspace,
                target=locked,
                meta={
                    "delta_available": data["delta_available"],
                    "delta_damaged": data["delta_damaged"],
                    "delta_lost": data["delta_lost"],
                    "reason": data["reason"],
                },
            )
        return Response(InventoryProductAdminSerializer(locked).data)


def _assert_box_in_makerspace(box, makerspace_id):
    """A product may only point at a box in its own makerspace (tenant isolation)."""
    if box is not None and box.makerspace_id != makerspace_id:
        raise ValidationError({"box": "Box belongs to a different makerspace."})


def _assert_category_in_makerspace(category, makerspace_id):
    """A product may only point at a category in its own makerspace."""
    if category is not None and category.makerspace_id != makerspace_id:
        raise ValidationError(
            {"category": "Category belongs to a different makerspace."}
        )
