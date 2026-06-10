from django.db import connection

from apps.inventory.models import InventoryProduct


class InsufficientStock(Exception):
    pass


def reserve_for_request(request):
    if not connection.in_atomic_block:
        raise RuntimeError("reserve_for_request must be called inside transaction.atomic().")

    items = list(request.items.order_by("product_id"))
    product_ids = [item.product_id for item in items]
    products = {
        product.pk: product
        for product in InventoryProduct.objects.select_for_update()
        .filter(pk__in=product_ids)
        .order_by("pk")
    }

    for item in items:
        quantity = item.accepted_quantity
        if quantity <= 0:
            continue

        product = products[item.product_id]
        if product.available_quantity < quantity:
            raise InsufficientStock(
                f"Insufficient stock for product {product.pk}: "
                f"requested {quantity}, available {product.available_quantity}."
            )

        product.available_quantity -= quantity
        product.reserved_quantity += quantity
        product.save(
            update_fields=[
                "available_quantity",
                "reserved_quantity",
                "updated_at",
            ]
        )


def issue_items(request):
    if not connection.in_atomic_block:
        raise RuntimeError("issue_items must be called inside transaction.atomic().")

    items = list(request.items.order_by("product_id"))
    product_ids = [item.product_id for item in items]
    products = {
        product.pk: product
        for product in InventoryProduct.objects.select_for_update()
        .filter(pk__in=product_ids)
        .order_by("pk")
    }

    for item in items:
        quantity = item.accepted_quantity
        if quantity <= 0:
            continue

        product = products[item.product_id]
        if product.reserved_quantity < quantity:
            raise InsufficientStock(
                f"Insufficient reserved stock for product {product.pk}: "
                f"requested {quantity}, reserved {product.reserved_quantity}."
            )

        product.reserved_quantity -= quantity
        product.issued_quantity += quantity
        product.save(
            update_fields=[
                "reserved_quantity",
                "issued_quantity",
                "updated_at",
            ]
        )

        item.issued_quantity = quantity
        item.save(update_fields=["issued_quantity"])
