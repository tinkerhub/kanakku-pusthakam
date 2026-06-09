import hashlib
import hmac
import time

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.models import User
from apps.apiclients.admin import ApiClientAdmin
from apps.apiclients.models import ApiClient
from apps.makerspaces.models import Makerspace, MakerspaceMembership

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _guard_v1_public(settings):
    # Container env pins HMAC_PROTECTED_PATH_PREFIXES to only /api/public/; the middleware
    # tests hit /api/v1/public/, so make the guarded-prefix list deterministic here.
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/public/", "/api/v1/public/"]


def test_issue_returns_raw_secret_and_stores_it_encrypted():
    s = Makerspace.objects.create(name="Kochi", slug="kochi")
    client, raw = ApiClient.issue(
        label="Kochi public", makerspace=s, allowed_origins=["http://localhost:5000"]
    )
    assert client.client_id.startswith("ck_")
    assert client.get_secret() == raw                 # round-trips
    assert bytes(client.secret_encrypted) != raw.encode()  # NOT plaintext at rest


def _admin_user(username, role=User.Role.ADMIN):
    return get_user_model().objects.create_user(
        username=username, email=f"{username}@e.com", role=role
    )


def test_admin_changelist_scoped_to_own_makerspace():
    a, b = Makerspace.objects.create(name="A", slug="a"), Makerspace.objects.create(name="B", slug="b")
    ApiClient.issue(label="A-client", makerspace=a)
    ApiClient.issue(label="B-client", makerspace=b)
    admin_user = _admin_user("scoped")
    MakerspaceMembership.objects.create(user=admin_user, makerspace=a, role="admin")

    req = APIRequestFactory().get("/")
    req.user = admin_user
    qs = ApiClientAdmin(ApiClient, AdminSite()).get_queryset(req)
    assert {c.makerspace_id for c in qs} == {a.id}  # cannot see B's client


PUBLIC = "/api/v1/public/makerspaces/"


def _sign(client_obj, raw_secret, path, origin):
    ts = str(int(time.time()))
    msg = b"\n".join([b"GET", path.encode(), ts.encode(), b""])
    sig = hmac.new(raw_secret.encode(), msg, hashlib.sha256).hexdigest()
    return {
        "HTTP_X_CLIENT_ID": client_obj.client_id,
        "HTTP_X_TIMESTAMP": ts,
        "HTTP_X_SIGNATURE": sig,
        "HTTP_ORIGIN": origin,
    }


@override_settings(API_CLIENT_AUTH_REQUIRED=True)
def test_valid_signed_client_passes():
    obj, raw = ApiClient.issue(label="ok", allowed_origins=["http://localhost:5000"])
    resp = APIClient().get(PUBLIC, **_sign(obj, raw, PUBLIC, "http://localhost:5000"))
    assert resp.status_code == 200


@override_settings(API_CLIENT_AUTH_REQUIRED=True)
def test_unknown_client_rejected():
    resp = APIClient().get(PUBLIC, HTTP_X_CLIENT_ID="ck_nope", HTTP_X_TIMESTAMP="1",
                           HTTP_X_SIGNATURE="x", HTTP_ORIGIN="http://localhost:5000")
    assert resp.status_code == 401


@override_settings(API_CLIENT_AUTH_REQUIRED=True)
def test_disallowed_origin_rejected():
    obj, raw = ApiClient.issue(label="ok2", allowed_origins=["http://localhost:5000"])
    resp = APIClient().get(PUBLIC, **_sign(obj, raw, PUBLIC, "https://evil.test"))
    assert resp.status_code == 401


@override_settings(API_CLIENT_AUTH_REQUIRED=True)
def test_inactive_client_rejected():
    obj, raw = ApiClient.issue(label="off", allowed_origins=["http://localhost:5000"])
    obj.is_active = False
    obj.save()
    resp = APIClient().get(PUBLIC, **_sign(obj, raw, PUBLIC, "http://localhost:5000"))
    assert resp.status_code == 401


def test_auth_not_required_lets_public_through():
    # Default API_CLIENT_AUTH_REQUIRED=False -> unsigned public request still works.
    Makerspace.objects.create(name="Open", slug="open", public_inventory_enabled=True)
    assert APIClient().get(PUBLIC).status_code == 200
