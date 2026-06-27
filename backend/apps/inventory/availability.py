from django.db import connection, transaction
from django.db.models import Count

from apps.inventory.models import InventoryAsset, InventoryProduct, TrackingMode


class InsufficientStock(Exception):
    pass


ASSET_QUANTITY_BUCKETS = {
    InventoryAsset.Status.AVAILABLE: "available_quantity",
    InventoryAsset.Status.RESERVED: "reserved_quantity",
    InventoryAsset.Status.ISSUED: "issued_quantity",
    InventoryAsset.Status.DAMAGED: "damaged_quantity",
    InventoryAsset.Status.LOST: "lost_quantity",
    InventoryAsset.Status.MAINTENANCE: "needs_fix_quantity",
}

ASSET_QUANTITY_FIELDS = tuple(dict.fromkeys(ASSET_QUANTITY_BUCKETS.values()))


def reconcile_individual_product_from_assets(product):
    """Make individual-tracked product buckets match serialized asset rows.

    Fork-specific reservation model (do NOT recompute reserved from asset status):
    an individual unit is reserved at the PRODUCT level (`reserved_quantity`) while its
    asset row stays AVAILABLE — assets only flip AVAILABLE->ISSUED at handover (see
    `reserve_for_request` / `assert_individual_assets_available`). So `reserved_quantity`
    is NOT derivable from asset status; recomputing it from rows (which never carry the
    RESERVED status here) would zero live reservations and let a reserved physical asset
    be allocated twice. We therefore PRESERVE `reserved_quantity`, recompute
    issued/damaged/lost/needs_fix from asset rows, and derive
    `available = AVAILABLE_assets - reserved_quantity` (reserved units are physically
    still AVAILABLE-status rows).
    """
    if product.tracking_mode != TrackingMode.INDIVIDUAL:
        return product

    status_counts = {
        row["status"]: row["count"]
        for row in (
            InventoryAsset.objects.filter(product_id=product.pk)
            .values("status")
            .annotate(count=Count("id"))
        )
    }
    available_assets = status_counts.get(InventoryAsset.Status.AVAILABLE, 0)
    reserved = product.reserved_quantity  # preserved — request-driven, not asset-derivable
    counts = {
        "issued_quantity": status_counts.get(InventoryAsset.Status.ISSUED, 0),
        "damaged_quantity": status_counts.get(InventoryAsset.Status.DAMAGED, 0),
        "lost_quantity": status_counts.get(InventoryAsset.Status.LOST, 0),
        "needs_fix_quantity": status_counts.get(InventoryAsset.Status.MAINTENANCE, 0),
        "available_quantity": max(0, available_assets - reserved),
    }
    # total = every serialized row; reserved units are already inside available_assets,
    # so add reserved back exactly once (available was reduced by it above).
    total = sum(counts.values()) + reserved
    changed = []
    for field, value in counts.items():
        if getattr(product, field) != value:
            setattr(product, field, value)
            changed.append(field)
    if product.total_quantity != total:
        product.total_quantity = total
        changed.append("total_quantity")

    if changed:
        product.save(update_fields=[*changed, "updated_at"])
    return product


def move_asset_status(asset, new_status):
    """Move one serialized asset between product quantity buckets.

    The caller must already be inside transaction.atomic() and hold the asset row
    lock. This service locks the product row before changing bucket counts.
    """
    if not connection.in_atomic_block:
        raise RuntimeError("move_asset_status must be called inside transaction.atomic().")
    old_status = asset.status
    if old_status == new_status:
        return asset
    old_bucket = ASSET_QUANTITY_BUCKETS.get(old_status)
    new_bucket = ASSET_QUANTITY_BUCKETS.get(new_status)
    if old_bucket is None or new_bucket is None:
        raise InsufficientStock(
            "Asset status transition is not backed by inventory quantity buckets."
        )

    product = InventoryProduct.objects.select_for_update().get(pk=asset.product_id)
    reconcile_individual_product_from_assets(product)
    product.refresh_from_db()
    old_value = getattr(product, old_bucket)
    if old_value < 1:
        raise InsufficientStock(
            f"Product {product.pk} has no {old_bucket} stock to move."
        )
    asset.status = new_status
    asset.save(update_fields=["status", "updated_at"])
    reconcile_individual_product_from_assets(product)
    return asset


def adjust_quantities(
    product, *, delta_available, delta_damaged, delta_lost, reason, actor
):
    """Apply signed deltas to a product's available/damaged/lost buckets, recompute
    total, record an InventoryAdjustment, and audit. Row-locked; refuses to make any
    bucket negative (raises InsufficientStock)."""
    with transaction.atomic():
        locked = InventoryProduct.objects.select_for_update().get(pk=product.pk)
        available = locked.available_quantity + delta_available
        damaged = locked.damaged_quantity + delta_damaged
        lost = locked.lost_quantity + delta_lost
        if available < 0 or damaged < 0 or lost < 0:
            raise InsufficientStock(
                "Quantity adjustment cannot make a bucket negative."
            )

        locked.available_quantity = available
        locked.damaged_quantity = damaged
        locked.lost_quantity = lost
        locked.total_quantity = (
            locked.available_quantity
            + locked.reserved_quantity
            + locked.issued_quantity
            + locked.damaged_quantity
            + locked.lost_quantity
            + locked.needs_fix_quantity
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

        from apps.audit import services as audit
        from apps.operations.models import InventoryAdjustment

        InventoryAdjustment.objects.create(
            makerspace=locked.makerspace,
            product=locked,
            delta_available=delta_available,
            delta_damaged=delta_damaged,
            delta_lost=delta_lost,
            reason=reason,
            created_by=actor,
        )
        audit.record(
            actor,
            "inventory.quantity_adjusted",
            makerspace=locked.makerspace,
            target=locked,
            meta={
                "delta_available": delta_available,
                "delta_damaged": delta_damaged,
                "delta_lost": delta_lost,
                "reason": reason,
            },
        )
    return locked


def issue_available(product, quantity):
    """Move `quantity` of a single product straight from available -> issued.

    The no-reservation flows (public self-checkout, admin direct handout) never go
    through accept/reserve, so they skip the reserved bucket. The caller must
    already hold a row lock on `product` (select_for_update) inside an atomic
    block; centralizing the math here keeps the never-below-zero invariant in one
    place instead of being open-coded in each workflow."""
    if not connection.in_atomic_block:
        raise RuntimeError("issue_available must be called inside transaction.atomic().")
    if product.available_quantity < quantity:
        raise InsufficientStock(
            f"Insufficient stock for product {product.pk}: "
            f"requested {quantity}, available {product.available_quantity}."
        )
    product.available_quantity -= quantity
    product.issued_quantity += quantity
    product.save(update_fields=["available_quantity", "issued_quantity", "updated_at"])


def return_to_available(product, quantity):
    """Move `quantity` of a single product back from issued -> available.

    Mirror of `issue_available` for the no-reservation return paths. Same locking
    contract as above."""
    if not connection.in_atomic_block:
        raise RuntimeError("return_to_available must be called inside transaction.atomic().")
    if product.issued_quantity < quantity:
        raise InsufficientStock(
            f"Insufficient issued stock for product {product.pk}: "
            f"returning {quantity}, issued {product.issued_quantity}."
        )
    product.issued_quantity -= quantity
    product.available_quantity += quantity
    product.save(update_fields=["issued_quantity", "available_quantity", "updated_at"])


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

    # Aggregate accepted quantity per product (a product may span multiple items).
    required_by_product = {}
    for item in items:
        if item.accepted_quantity > 0:
            required_by_product[item.product_id] = (
                required_by_product.get(item.product_id, 0) + item.accepted_quantity
            )

    for product_id in sorted(required_by_product):
        quantity = required_by_product[product_id]
        product = products[product_id]

        # Individual-asset guard runs UNDER the same row lock as the reservation
        # update, reading the freshly-locked reserved_quantity as the committed
        # baseline. A concurrent accept for the same product blocks on this lock
        # until we commit, then re-reads the incremented baseline and is rejected —
        # closing the check-then-reserve race a standalone pre-check would leave open.
        assert_individual_assets_available(product, quantity)

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


def assert_individual_assets_available(product, required_qty):
    """Fail fast when quantity buckets outpace serialized asset rows.

    Individual-mode asset rows only flip AVAILABLE->ISSUED at handover, so a unit
    that is accepted-but-not-yet-issued still leaves its asset row AVAILABLE while
    `reserved_quantity` is incremented. Counting AVAILABLE assets alone would let a
    drifted-high quantity bucket reserve the same physical asset for two requests;
    subtract the already-reserved (committed-but-unissued) units so the available
    physical assets must cover this request PLUS every outstanding reservation."""
    required_qty = int(required_qty)
    if product.tracking_mode != TrackingMode.INDIVIDUAL or required_qty <= 0:
        return

    available_assets = InventoryAsset.objects.filter(
        product_id=product.pk,
        status=InventoryAsset.Status.AVAILABLE,
    ).count()
    already_reserved = max(int(getattr(product, "reserved_quantity", 0) or 0), 0)
    if available_assets < required_qty + already_reserved:
        raise InsufficientStock(
            f"Insufficient available assets for product {product.pk}: "
            f"requested {required_qty}, already reserved {already_reserved}, "
            f"available assets {available_assets}."
        )


# Dispositions for units rejected as broken at handover.
REJECT_NEEDS_FIX = "needs_fix"  # park on the to-be-fixed shelf (stays in total)
REJECT_REMOVE = "remove"  # scrap it out of inventory entirely (total drops)


def issue_items(request, rejects_by_item=None):
    """Move each accepted item out of `reserved`.

    `rejects_by_item` maps HardwareRequestItem.id -> (broken, disposition) for units
    rejected as broken at handover. Broken units leave `reserved`; with disposition
    'needs_fix' they go to the needs-fix shelf (stays within total), with 'remove' they
    are scrapped (total drops). The rest of the accepted quantity is issued normally.
    """
    if not connection.in_atomic_block:
        raise RuntimeError("issue_items must be called inside transaction.atomic().")

    rejects_by_item = rejects_by_item or {}
    items = list(request.items.order_by("product_id"))
    product_ids = [item.product_id for item in items]
    products = {
        product.pk: product
        for product in InventoryProduct.objects.select_for_update()
        .filter(pk__in=product_ids)
        .order_by("pk")
    }

    for item in items:
        accepted = item.accepted_quantity
        if accepted <= 0:
            continue

        broken, disposition = rejects_by_item.get(item.id, (0, REJECT_NEEDS_FIX))
        broken = max(0, int(broken))
        if broken > accepted:
            raise InsufficientStock(
                f"Cannot reject {broken} as broken: only {accepted} accepted."
            )
        issued = accepted - broken

        product = products[item.product_id]
        if product.reserved_quantity < accepted:
            raise InsufficientStock(
                f"Insufficient reserved stock for product {product.pk}: "
                f"requested {accepted}, reserved {product.reserved_quantity}."
            )

        product.reserved_quantity -= accepted
        product.issued_quantity += issued
        update_fields = ["reserved_quantity", "issued_quantity", "updated_at"]
        if broken and disposition == REJECT_REMOVE:
            product.total_quantity -= broken
            update_fields.append("total_quantity")
        elif broken:
            product.needs_fix_quantity += broken
            update_fields.append("needs_fix_quantity")
        product.save(update_fields=update_fields)

        item.issued_quantity = issued
        item.needs_fix_quantity = 0 if disposition == REJECT_REMOVE else broken
        item.save(update_fields=["issued_quantity", "needs_fix_quantity"])


def repair_from_needs_fix(product, quantity):
    """Move repaired units off the to-be-fixed shelf back into available stock."""
    if not connection.in_atomic_block:
        raise RuntimeError("repair_from_needs_fix must be called inside transaction.atomic().")
    locked = InventoryProduct.objects.select_for_update().get(pk=product.pk)
    if quantity <= 0 or locked.needs_fix_quantity < quantity:
        raise InsufficientStock(
            f"Cannot repair {quantity}: only {locked.needs_fix_quantity} on the shelf."
        )
    locked.needs_fix_quantity -= quantity
    locked.available_quantity += quantity
    locked.save(update_fields=["needs_fix_quantity", "available_quantity", "updated_at"])
    return locked


def move_available_to_needs_fix(product, quantity):
    """Move available units out of circulation onto the to-be-fixed shelf."""
    if not connection.in_atomic_block:
        raise RuntimeError("move_available_to_needs_fix must be called inside transaction.atomic().")
    locked = InventoryProduct.objects.select_for_update().get(pk=product.pk)
    if quantity <= 0 or locked.available_quantity < quantity:
        raise InsufficientStock(
            f"Cannot move {quantity}: only {locked.available_quantity} available."
        )
    locked.available_quantity -= quantity
    locked.needs_fix_quantity += quantity
    locked.save(update_fields=["available_quantity", "needs_fix_quantity", "updated_at"])
    return locked


def scrap_from_needs_fix(product, quantity):
    """Remove unrepairable units from the to-be-fixed shelf and from inventory (total drops)."""
    if not connection.in_atomic_block:
        raise RuntimeError("scrap_from_needs_fix must be called inside transaction.atomic().")
    locked = InventoryProduct.objects.select_for_update().get(pk=product.pk)
    if quantity <= 0 or locked.needs_fix_quantity < quantity:
        raise InsufficientStock(
            f"Cannot scrap {quantity}: only {locked.needs_fix_quantity} on the shelf."
        )
    locked.needs_fix_quantity -= quantity
    locked.total_quantity -= quantity
    locked.save(update_fields=["needs_fix_quantity", "total_quantity", "updated_at"])
    return locked


def return_items(request, resolutions):
    if not connection.in_atomic_block:
        raise RuntimeError("return_items must be called inside transaction.atomic().")

    items = [resolution["item"] for resolution in resolutions]
    product_ids = [item.product_id for item in items]
    products = {
        product.pk: product
        for product in InventoryProduct.objects.select_for_update()
        .filter(pk__in=product_ids)
        .order_by("pk")
    }

    for resolution in resolutions:
        item = resolution["item"]
        returned = resolution["returned"]
        damaged = resolution["damaged"]
        missing = resolution["missing"]
        quantity = returned + damaged + missing
        if quantity <= 0:
            continue

        product = products[item.product_id]
        if product.issued_quantity < quantity:
            raise InsufficientStock(
                f"Insufficient issued stock for product {product.pk}: "
                f"returning {quantity}, issued {product.issued_quantity}."
            )

        product.issued_quantity -= quantity
        product.available_quantity += returned
        product.damaged_quantity += damaged
        product.lost_quantity += missing
        product.save(
            update_fields=[
                "issued_quantity",
                "available_quantity",
                "damaged_quantity",
                "lost_quantity",
                "updated_at",
            ]
        )

        item.returned_quantity += returned
        item.damaged_quantity += damaged
        item.missing_quantity += missing
        item.save(
            update_fields=[
                "returned_quantity",
                "damaged_quantity",
                "missing_quantity",
            ]
        )
