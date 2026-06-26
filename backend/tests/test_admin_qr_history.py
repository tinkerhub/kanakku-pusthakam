import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.boxes.models import QrCode, QrScanEvent
from apps.inventory.models import InventoryAsset, TrackingMode
from apps.makerspaces.models import MakerspaceMembership
from tests.return_helpers import authenticated_client, make_member, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def _qr(makerspace, target_type, target_id, payload):
    return QrCode.objects.create(
        makerspace=makerspace,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
    )


def _scan(makerspace, qr, actor, context=QrScanEvent.Context.INVENTORY_CHECK):
    return QrScanEvent.objects.create(
        makerspace=makerspace,
        qr_code=qr,
        actor=actor,
        context=context,
    )


def test_product_qr_history_is_audit_gated_scoped_redacted_and_capped():
    makerspace = make_space("product-qr-history")
    other_space = make_space("product-qr-history-other")
    inventory_manager = make_member(
        "product-qr-history-inventory",
        makerspace,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
        role=User.Role.REQUESTER,
    )
    guest_admin = make_member(
        "product-qr-history-guest",
        makerspace,
        membership_role=MakerspaceMembership.Role.GUEST_ADMIN,
        role=User.Role.GUEST_ADMIN,
    )
    product = make_product(makerspace, name="QR Product")
    other_product = make_product(makerspace, name="Other QR Product")
    foreign_product = make_product(other_space, name="Foreign QR Product")
    qr = _qr(makerspace, QrCode.TargetType.PRODUCT, product.id, "product-secret")
    other_qr = _qr(makerspace, QrCode.TargetType.PRODUCT, other_product.id, "other-secret")
    foreign_qr = _qr(other_space, QrCode.TargetType.PRODUCT, foreign_product.id, "foreign-secret")
    for _ in range(105):
        _scan(makerspace, qr, inventory_manager)
    _scan(makerspace, other_qr, inventory_manager, QrScanEvent.Context.SCANNER_LOOKUP)
    _scan(
        other_space,
        foreign_qr,
        make_member("product-qr-history-foreign-staff", other_space),
        QrScanEvent.Context.RETURN,
    )

    response = authenticated_client(inventory_manager).get(
        reverse("admin-inventory-qr-history", kwargs={"pk": product.id})
    )
    guest_response = authenticated_client(guest_admin).get(
        reverse("admin-inventory-qr-history", kwargs={"pk": product.id})
    )

    assert response.status_code == 200
    assert response.data["product"] == product.id
    assert len(response.data["scans"]) == 100
    assert {scan["source"] for scan in response.data["scans"]} == {"qr_scan"}
    assert {scan["context"] for scan in response.data["scans"]} == {QrScanEvent.Context.INVENTORY_CHECK}
    assert "payload" not in response.data["scans"][0]
    assert "product-secret" not in str(response.data)
    assert "other-secret" not in str(response.data)
    assert "foreign-secret" not in str(response.data)
    assert guest_response.status_code in {403, 404}


def test_asset_qr_history_is_audit_gated_scoped_and_redacted():
    makerspace = make_space("asset-qr-history")
    other_space = make_space("asset-qr-history-other")
    staff = make_member("asset-qr-history-staff", makerspace)
    product = make_product(
        makerspace,
        name="Asset QR Product",
        tracking_mode=TrackingMode.INDIVIDUAL,
    )
    asset = InventoryAsset.objects.create(
        makerspace=makerspace,
        product=product,
        asset_tag="A-1",
    )
    qr = _qr(makerspace, QrCode.TargetType.ASSET, asset.id, "asset-secret")
    _scan(makerspace, qr, staff, QrScanEvent.Context.RETURN)
    outsider = make_member("asset-qr-history-outsider", other_space)
    guest_admin = make_member(
        "asset-qr-history-guest",
        makerspace,
        membership_role=MakerspaceMembership.Role.GUEST_ADMIN,
        role=User.Role.GUEST_ADMIN,
    )

    own_response = authenticated_client(staff).get(
        reverse("admin-inventory-asset-qr-history", kwargs={"pk": asset.id})
    )
    cross_response = authenticated_client(outsider).get(
        reverse("admin-inventory-asset-qr-history", kwargs={"pk": asset.id})
    )
    guest_response = authenticated_client(guest_admin).get(
        reverse("admin-inventory-asset-qr-history", kwargs={"pk": asset.id})
    )

    assert own_response.status_code == 200
    assert own_response.data["asset"] == asset.id
    assert len(own_response.data["scans"]) == 1
    assert own_response.data["scans"][0]["context"] == QrScanEvent.Context.RETURN
    assert "payload" not in own_response.data["scans"][0]
    assert "asset-secret" not in str(own_response.data)
    assert cross_response.status_code == 404
    assert guest_response.status_code in {403, 404}


def test_superadmin_can_read_visible_qr_history_but_not_hidden_makerspace_scan_pii():
    visible_space = make_space("qr-history-visible")
    hidden_space = make_space("qr-history-hidden")
    hidden_space.superadmin_access_enabled = False
    hidden_space.save(update_fields=["superadmin_access_enabled"])
    superadmin = make_user(
        "qr-history-superadmin",
        role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )
    visible_product = make_product(visible_space, name="Visible QR Product")
    hidden_product = make_product(hidden_space, name="Hidden QR Product")
    visible_qr = _qr(visible_space, QrCode.TargetType.PRODUCT, visible_product.id, "visible-secret")
    hidden_qr = _qr(hidden_space, QrCode.TargetType.PRODUCT, hidden_product.id, "hidden-secret")
    _scan(visible_space, visible_qr, superadmin)
    _scan(hidden_space, hidden_qr, make_member("hidden-space-staff", hidden_space))
    client = authenticated_client(superadmin)

    visible_response = client.get(reverse("admin-inventory-qr-history", kwargs={"pk": visible_product.id}))
    hidden_response = client.get(reverse("admin-inventory-qr-history", kwargs={"pk": hidden_product.id}))

    assert visible_response.status_code == 200
    assert len(visible_response.data["scans"]) == 1
    assert hidden_response.status_code == 404
