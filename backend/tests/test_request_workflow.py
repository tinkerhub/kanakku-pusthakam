import uuid
from collections.abc import Mapping
from unittest.mock import Mock

import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.boxes.models import Box
from apps.checkin.client import CheckinDenied, CheckinResult, CheckinUnavailable
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace, MakerspaceMembership

pytestmark = pytest.mark.django_db


def make_user(username, role=User.Role.REQUESTER, **kw):
    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@e.com",
        role=role,
        **kw,
    )


def make_space(slug):
    return Makerspace.objects.create(name=slug, slug=slug)


def make_member(
    username,
    makerspace,
    membership_role=MakerspaceMembership.Role.ADMIN,
    role=User.Role.ADMIN,
):
    user = make_user(username, role=role, access_status=User.AccessStatus.ACTIVE)
    MakerspaceMembership.objects.create(
        user=user,
        makerspace=makerspace,
        role=membership_role,
    )
    return user


def make_product(makerspace, name="Oscilloscope", **overrides):
    defaults = {
        "makerspace": makerspace,
        "name": name,
        "description": f"{name} description",
        "total_quantity": 5,
        "available_quantity": 5,
        "reserved_quantity": 0,
        "is_public": True,
        "is_archived": False,
    }
    defaults.update(overrides)
    return InventoryProduct.objects.create(**defaults)


def make_hardware_request(
    makerspace,
    product,
    requester=None,
    quantity=1,
    status=HardwareRequest.Status.PENDING_APPROVAL,
):
    requester = requester or make_user(
        f"requester-{makerspace.slug}-{uuid.uuid4().hex[:8]}",
        access_status=User.AccessStatus.ACTIVE,
    )
    request = HardwareRequest.objects.create(
        makerspace=makerspace,
        requester=requester,
        requester_username=requester.username,
        status=status,
    )
    HardwareRequestItem.objects.create(
        request=request,
        product=product,
        requested_quantity=quantity,
    )
    return request


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def public_submit_url(makerspace):
    return f"/api/v1/public/{makerspace.slug}/requests"


def public_status_url(public_token):
    return f"/api/v1/public/requests/{public_token}/status"


def pending_requests_url(makerspace):
    return f"/api/v1/admin/makerspace/{makerspace.id}/pending-requests"


def accepted_requests_url(makerspace):
    return f"/api/v1/admin/makerspace/{makerspace.id}/accepted-requests"


def accept_url(hardware_request):
    return f"/api/v1/admin/requests/{hardware_request.id}/accept"


def reject_url(hardware_request):
    return f"/api/v1/admin/requests/{hardware_request.id}/reject"


def submit_payload(identifier, product, quantity=1):
    return {
        "identifier": identifier,
        "requested_for": "Bench diagnostics",
        "items": [{"product_id": product.id, "quantity": quantity}],
    }


def json_keys(data):
    keys = set()
    if isinstance(data, Mapping):
        for key, value in data.items():
            keys.add(key)
            keys.update(json_keys(value))
    elif isinstance(data, list):
        for item in data:
            keys.update(json_keys(item))
    return keys


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_restricted_requester_cannot_submit():
    makerspace = make_space("restricted-submit")
    product = make_product(makerspace)
    make_user(
        "restricted-requester",
        access_status=User.AccessStatus.RESTRICTED,
        external_checkin_user_id="ext-r",
    )

    response = APIClient().post(
        public_submit_url(makerspace),
        submit_payload("ext-r", product),
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "requester_blocked"
    assert HardwareRequest.objects.count() == 0


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_suspended_requester_cannot_submit():
    makerspace = make_space("suspended-submit")
    product = make_product(makerspace)
    make_user(
        "suspended-requester",
        access_status=User.AccessStatus.SUSPENDED,
        external_checkin_user_id="ext-s",
    )

    response = APIClient().post(
        public_submit_url(makerspace),
        submit_payload("ext-s", product),
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "requester_blocked"
    assert HardwareRequest.objects.count() == 0


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_successful_submission_creates_pending_request_items_audit_and_notifies(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    makerspace = make_space("successful-submit")
    product = make_product(makerspace, name="Logic Analyzer")
    notify = Mock()
    monkeypatch.setattr(
        "apps.hardware_requests.notifications.notify_request_submitted",
        notify,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = APIClient().post(
            public_submit_url(makerspace),
            submit_payload("ext-ok", product, quantity=2),
            format="json",
        )

    assert response.status_code == 201
    assert set(response.data) == {"public_token", "status"}
    assert response.data["status"] == HardwareRequest.Status.PENDING_APPROVAL
    assert len(callbacks) == 1
    hardware_request = HardwareRequest.objects.get()
    assert str(hardware_request.public_token) == response.data["public_token"]
    assert hardware_request.status == HardwareRequest.Status.PENDING_APPROVAL
    item = hardware_request.items.get()
    assert item.product == product
    assert item.requested_quantity == 2
    audit = AuditLog.objects.get(action="request.submitted")
    assert audit.makerspace == makerspace
    assert audit.target_id == str(hardware_request.id)
    notify.assert_called_once_with(hardware_request)


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_checkin_unavailable_returns_503_and_creates_no_request(monkeypatch):
    makerspace = make_space("checkin-unavailable")
    product = make_product(makerspace)
    monkeypatch.setattr(
        "apps.checkin.client.verify",
        Mock(side_effect=CheckinUnavailable("service down")),
    )
    before_count = HardwareRequest.objects.count()

    response = APIClient().post(
        public_submit_url(makerspace),
        submit_payload("ext-down", product),
        format="json",
    )

    assert response.status_code == 503
    assert response.data["code"] == "checkin_unavailable"
    assert HardwareRequest.objects.count() == before_count


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_checkin_denied_returns_403_and_creates_no_request(monkeypatch):
    makerspace = make_space("checkin-denied")
    product = make_product(makerspace)
    monkeypatch.setattr(
        "apps.checkin.client.verify",
        Mock(side_effect=CheckinDenied("not checked in")),
    )

    response = APIClient().post(
        public_submit_url(makerspace),
        submit_payload("ext-denied", product),
        format="json",
    )

    assert response.status_code == 403
    assert response.data["code"] == "checkin_denied"
    assert HardwareRequest.objects.count() == 0


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_duplicate_product_lines_in_one_submission_return_400():
    makerspace = make_space("duplicate-lines")
    product = make_product(makerspace)
    payload = {
        "identifier": "ext-duplicate",
        "items": [
            {"product_id": product.id, "quantity": 1},
            {"product_id": product.id, "quantity": 2},
        ],
    }

    response = APIClient().post(
        public_submit_url(makerspace),
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert HardwareRequest.objects.count() == 0


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
@pytest.mark.parametrize(
    ("name", "product_overrides", "other_space"),
    [
        ("private", {"is_public": False}, False),
        ("archived", {"is_archived": True}, False),
        ("other-space", {}, True),
    ],
)
def test_unrequestable_product_returns_400_and_creates_no_request(
    name,
    product_overrides,
    other_space,
):
    makerspace = make_space(f"unrequestable-{name}")
    product_space = make_space(f"unrequestable-{name}-other") if other_space else makerspace
    product = make_product(product_space, **product_overrides)

    response = APIClient().post(
        public_submit_url(makerspace),
        submit_payload(f"ext-{name}", product),
        format="json",
    )

    assert response.status_code == 400
    assert HardwareRequest.objects.count() == 0


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_public_status_by_token_returns_strict_allowlist_and_unknown_token_404():
    makerspace = make_space("public-status")
    box = Box.objects.create(
        makerspace=makerspace,
        label="Secure Box",
        location="Hidden Shelf",
    )
    product = make_product(
        makerspace,
        name="Thermal Camera",
        box=box,
        storage_location="Locked cabinet A",
    )
    requester = make_user(
        "status-requester",
        access_status=User.AccessStatus.ACTIVE,
        phone="+15551234567",
    )
    hardware_request = make_hardware_request(
        makerspace,
        product,
        requester=requester,
        quantity=3,
    )

    response = APIClient().get(public_status_url(hardware_request.public_token))

    assert response.status_code == 200
    assert set(response.data) == {
        "status",
        "rejection_reason",
        "created_at",
        "items",
    }
    assert len(response.data["items"]) == 1
    assert set(response.data["items"][0]) == {"product_name", "requested_quantity"}
    all_keys = json_keys(response.data)
    for forbidden_key in {
        "id",
        "product_id",
        "box",
        "code",
        "storage_location",
        "makerspace_id",
        "requester",
        "requester_username",
        "email",
        "phone",
        "accepted_quantity",
        "issued_quantity",
        "public_token",
    }:
        assert forbidden_key not in all_keys

    missing = APIClient().get(public_status_url(uuid.uuid4()))
    assert missing.status_code == 404


def test_admin_accept_reserves_inventory_and_writes_audit():
    makerspace = make_space("accept-reserves")
    product = make_product(makerspace, total_quantity=5, available_quantity=5)
    hardware_request = make_hardware_request(makerspace, product, quantity=2)
    admin = make_member("accept-admin", makerspace)

    response = authenticated_client(admin).post(accept_url(hardware_request), format="json")

    assert response.status_code == 200
    assert response.data["status"] == HardwareRequest.Status.ACCEPTED
    product.refresh_from_db()
    assert product.available_quantity == 3
    assert product.reserved_quantity == 2
    hardware_request.refresh_from_db()
    assert hardware_request.status == HardwareRequest.Status.ACCEPTED
    item = hardware_request.items.get()
    assert item.accepted_quantity == 2
    audit = AuditLog.objects.get(action="request.accepted")
    assert audit.makerspace == makerspace
    assert audit.target_id == str(hardware_request.id)


def test_accept_with_insufficient_stock_rolls_back_and_returns_409():
    makerspace = make_space("insufficient-stock")
    product = make_product(makerspace, total_quantity=1, available_quantity=1)
    hardware_request = make_hardware_request(makerspace, product, quantity=3)
    admin = make_member("insufficient-admin", makerspace)

    response = authenticated_client(admin).post(accept_url(hardware_request), format="json")

    assert response.status_code == 409
    assert response.data["code"] == "insufficient_stock"
    product.refresh_from_db()
    assert product.available_quantity == 1
    assert product.reserved_quantity == 0
    hardware_request.refresh_from_db()
    assert hardware_request.status == HardwareRequest.Status.PENDING_APPROVAL
    item = hardware_request.items.get()
    assert item.accepted_quantity == 0
    assert AuditLog.objects.filter(action="request.accepted").count() == 0


def test_cross_tenant_accept_returns_404_without_leaking_request_existence():
    own_space = make_space("cross-tenant-own")
    other_space = make_space("cross-tenant-other")
    product = make_product(other_space)
    hardware_request = make_hardware_request(other_space, product)
    admin = make_member("cross-tenant-admin", own_space)

    response = authenticated_client(admin).post(accept_url(hardware_request), format="json")

    assert response.status_code == 404


def test_wrong_action_accept_in_own_makerspace_returns_403_for_guest_and_requester():
    makerspace = make_space("wrong-action")
    product = make_product(makerspace)
    hardware_request = make_hardware_request(makerspace, product)
    guest_admin = make_member(
        "wrong-action-guest",
        makerspace,
        membership_role=MakerspaceMembership.Role.GUEST_ADMIN,
        role=User.Role.GUEST_ADMIN,
    )
    plain_requester = make_user("wrong-action-requester", access_status=User.AccessStatus.ACTIVE)

    response = authenticated_client(guest_admin).post(
        accept_url(hardware_request),
        format="json",
    )
    assert response.status_code == 403

    response = authenticated_client(plain_requester).post(
        accept_url(hardware_request),
        format="json",
    )
    assert response.status_code == 403


def test_guest_admin_cannot_reject_but_can_get_accepted_queue_not_pending_queue():
    makerspace = make_space("guest-queues")
    product = make_product(makerspace)
    pending_request = make_hardware_request(makerspace, product)
    accepted_request = make_hardware_request(
        makerspace,
        product,
        status=HardwareRequest.Status.ACCEPTED,
    )
    guest_admin = make_member(
        "guest-queue-admin",
        makerspace,
        membership_role=MakerspaceMembership.Role.GUEST_ADMIN,
        role=User.Role.GUEST_ADMIN,
    )
    client = authenticated_client(guest_admin)

    response = client.post(
        reject_url(pending_request),
        {"reason": "No longer eligible."},
        format="json",
    )
    assert response.status_code == 403

    response = client.get(accepted_requests_url(makerspace))
    assert response.status_code == 200
    assert [item["id"] for item in response.data["results"]] == [accepted_request.id]

    response = client.get(pending_requests_url(makerspace))
    assert response.status_code == 403


def test_reject_requires_reason_and_valid_reason_rejects_without_inventory_change():
    makerspace = make_space("reject-reason")
    product = make_product(makerspace, total_quantity=4, available_quantity=4)
    hardware_request = make_hardware_request(makerspace, product, quantity=2)
    admin = make_member("reject-admin", makerspace)
    client = authenticated_client(admin)

    response = client.post(reject_url(hardware_request), {"reason": ""}, format="json")
    assert response.status_code == 400

    response = client.post(
        reject_url(hardware_request),
        {"reason": "Missing training clearance."},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == HardwareRequest.Status.REJECTED
    assert response.data["rejection_reason"] == "Missing training clearance."
    product.refresh_from_db()
    assert product.available_quantity == 4
    assert product.reserved_quantity == 0
    hardware_request.refresh_from_db()
    assert hardware_request.status == HardwareRequest.Status.REJECTED
    assert hardware_request.rejection_reason == "Missing training clearance."
    assert AuditLog.objects.get(action="request.rejected").target_id == str(
        hardware_request.id
    )


def test_availability_never_goes_below_zero_for_sequential_accepts():
    makerspace = make_space("sequential-accepts")
    product = make_product(makerspace, total_quantity=1, available_quantity=1)
    first_request = make_hardware_request(makerspace, product, quantity=1)
    second_request = make_hardware_request(makerspace, product, quantity=1)
    admin = make_member("sequential-admin", makerspace)
    client = authenticated_client(admin)

    first_response = client.post(accept_url(first_request), format="json")
    second_response = client.post(accept_url(second_request), format="json")

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.data["code"] == "insufficient_stock"
    product.refresh_from_db()
    assert product.available_quantity == 0
    assert product.reserved_quantity == 1
    second_request.refresh_from_db()
    assert second_request.status == HardwareRequest.Status.PENDING_APPROVAL


def test_superadmin_can_accept_across_makerspaces_without_membership():
    makerspace = make_space("superadmin-accept")
    product = make_product(makerspace)
    hardware_request = make_hardware_request(makerspace, product, quantity=1)
    superadmin = make_user(
        "request-superadmin",
        role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )

    response = authenticated_client(superadmin).post(
        accept_url(hardware_request),
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == HardwareRequest.Status.ACCEPTED


@override_settings(API_CLIENT_AUTH_REQUIRED=False)
def test_request_submit_throttle_returns_429_on_second_rapid_submit(settings, monkeypatch):
    cache.clear()
    rest_framework_settings = dict(django_settings.REST_FRAMEWORK)
    rest_framework_settings["DEFAULT_THROTTLE_RATES"] = {
        **django_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "request_submit": "1/min",
    }
    settings.REST_FRAMEWORK = rest_framework_settings
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        rest_framework_settings["DEFAULT_THROTTLE_RATES"],
    )
    makerspace = make_space("submit-throttle")
    product = make_product(makerspace)
    verify = Mock(
        side_effect=[
            CheckinResult(username="first", external_id="throttle-first"),
            CheckinResult(username="second", external_id="throttle-second"),
        ]
    )
    monkeypatch.setattr("apps.checkin.client.verify", verify)
    client = APIClient()

    first = client.post(
        public_submit_url(makerspace),
        submit_payload("first", product),
        format="json",
    )
    second = client.post(
        public_submit_url(makerspace),
        submit_payload("second", product),
        format="json",
    )

    assert first.status_code == 201
    assert second.status_code == 429


def test_suspended_staff_cannot_view_accepted_queue():
    # Stage-4 review fix (P2-2): the handover queue must enforce active access_status,
    # not just authentication + ISSUE_REQUEST membership.
    makerspace = make_space("suspended-staff-queue")
    guest = make_member(
        "suspended-guest",
        makerspace,
        membership_role=MakerspaceMembership.Role.GUEST_ADMIN,
        role=User.Role.GUEST_ADMIN,
    )
    guest.access_status = User.AccessStatus.SUSPENDED
    guest.save(update_fields=["access_status"])

    response = authenticated_client(guest).get(accepted_requests_url(makerspace))

    assert response.status_code == 403
