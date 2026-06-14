from collections import Counter

from django.utils import timezone

from apps.accounts.models import User
from apps.boxes.models import Box, QrCode
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.hardware_requests.workflow_errors import RequestValidationError, RequesterBlocked
from apps.hardware_requests.workflow_utils import get_or_create_requester
from apps.inventory import availability
from apps.inventory.models import InventoryAsset, InventoryProduct


def _requester(external_id):
    requester = get_or_create_requester(external_id)
    if requester.access_status != User.AccessStatus.ACTIVE:
        raise RequesterBlocked("Requester is not active.")
    return requester


def _locked_qr(makerspace, payload):
    qr = (
        QrCode.objects.select_for_update()
        .filter(payload=payload, makerspace=makerspace, status=QrCode.Status.ACTIVE)
        .first()
    )
    if qr is None:
        raise RequestValidationError("QR code is not active for this makerspace.")
    return qr


def _checkout_target(qr):
    if qr.target_type == QrCode.TargetType.PRODUCT:
        product = _eligible_product(qr.target_id, qr.makerspace)
        _issue_product(product, 1)
        return product.name, {product: 1}, []
    if qr.target_type == QrCode.TargetType.ASSET:
        asset = _eligible_asset(qr.target_id, qr.makerspace)
        _issue_product(asset.product, 1)
        asset.status = InventoryAsset.Status.ISSUED
        asset.save(update_fields=["status", "updated_at"])
        return asset.asset_tag, {asset.product: 1}, [asset.id]
    return _checkout_box(qr)


def _checkout_box(qr):
    box = Box.objects.select_for_update().filter(pk=qr.target_id, makerspace=qr.makerspace).first()
    if box is None or not box.is_active:
        raise RequestValidationError("Box is not available for public self-checkout.")
    assets = list(
        InventoryAsset.objects.select_for_update()
        .select_related("product")
        .filter(
            box=box,
            status=InventoryAsset.Status.AVAILABLE,
            public_self_checkout_enabled=True,
            product__is_public=True,
            product__is_archived=False,
            product__public_self_checkout_enabled=True,
        )
    )
    if assets:
        # The assets were loaded with select_related("product") but that does NOT lock
        # the product rows. issue_available() requires the caller to hold a row lock, so
        # re-fetch the distinct products with select_for_update (in pk order to avoid
        # deadlocks) before mutating their quantity buckets.
        product_ids = {asset.product_id for asset in assets}
        locked_products = {
            product.pk: product
            for product in InventoryProduct.objects.select_for_update()
            .filter(pk__in=product_ids)
            .order_by("pk")
        }
        quantities = Counter(locked_products[asset.product_id] for asset in assets)
        for product, quantity in quantities.items():
            _issue_product(product, quantity)
        InventoryAsset.objects.filter(pk__in=[asset.id for asset in assets]).update(
            status=InventoryAsset.Status.ISSUED
        )
        return box.label, dict(quantities), [asset.id for asset in assets]

    products = list(
        InventoryProduct.objects.select_for_update().filter(
            box=box,
            is_public=True,
            is_archived=False,
            public_self_checkout_enabled=True,
            available_quantity__gte=1,
        )
    )
    if not products:
        raise RequestValidationError("Box has no public self-checkout items.")
    for product in products:
        _issue_product(product, 1)
    return box.label, {product: 1 for product in products}, []


def _eligible_product(pk, makerspace):
    product = InventoryProduct.objects.select_for_update().filter(pk=pk, makerspace=makerspace).first()
    if (
        product is None
        or not product.is_public
        or product.is_archived
        or not product.public_self_checkout_enabled
    ):
        raise RequestValidationError("Tool is not enabled for public self-checkout.")
    return product


def _eligible_asset(pk, makerspace):
    asset = (
        InventoryAsset.objects.select_for_update()
        .select_related("product")
        .filter(pk=pk, makerspace=makerspace)
        .first()
    )
    if asset is None or asset.status != InventoryAsset.Status.AVAILABLE:
        raise RequestValidationError("Asset is not available for public self-checkout.")
    if not asset.public_self_checkout_enabled:
        raise RequestValidationError("Asset is not enabled for public self-checkout.")
    asset.product = _eligible_product(asset.product_id, makerspace)
    return asset


def _issue_product(product, quantity):
    # Friendly public-facing guard (-> 400) before delegating the actual count
    # mutation to the Inventory Availability module, which owns the math.
    if product.available_quantity < quantity:
        raise RequestValidationError("Tool is not currently available.")
    availability.issue_available(product, quantity)


def _issued_request(
    makerspace,
    requester,
    requester_username,
    product_quantities,
    *,
    requested_for="Public QR self-checkout",
    issued_by=None,
):
    return _create_issued_request(
        makerspace,
        requester,
        requester_username,
        product_quantities,
        requested_for=requested_for,
        issued_by=issued_by or requester,
    )


def _create_issued_request(
    makerspace,
    requester,
    requester_username,
    product_quantities,
    *,
    requested_for,
    issued_by,
):
    request = HardwareRequest.objects.create(
        makerspace=makerspace,
        requester=requester,
        requester_username=requester_username,
        status=HardwareRequest.Status.ISSUED,
        requested_for=requested_for,
        issued_by=issued_by,
        issued_at=timezone.now(),
    )
    HardwareRequestItem.objects.bulk_create(
        [
            HardwareRequestItem(
                request=request,
                product=product,
                requested_quantity=quantity,
                accepted_quantity=quantity,
                issued_quantity=quantity,
            )
            for product, quantity in product_quantities.items()
        ]
    )
    return request


def _return_request_items(request):
    for item in request.items.select_related("product").select_for_update():
        outstanding = item.issued_quantity - item.returned_quantity
        if outstanding <= 0:
            continue
        product = InventoryProduct.objects.select_for_update().get(pk=item.product_id)
        availability.return_to_available(product, outstanding)
        item.returned_quantity += outstanding
        item.save(update_fields=["returned_quantity"])
