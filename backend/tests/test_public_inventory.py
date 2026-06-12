import hashlib
import hmac

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory.models import InventoryProduct, PublicAvailabilityMode
from apps.makerspaces.models import Makerspace


pytestmark = pytest.mark.django_db

PUBLIC_PRODUCT_FIELDS = {"id", "name", "description", "availability"}


def test_public_lookup_prefers_slug_over_colliding_public_code():
    # A user-controlled slug can collide with another makerspace's 4-char public_code.
    # The lookup must resolve deterministically (slug wins) instead of raising
    # MultipleObjectsReturned -> 500.
    from apps.makerspaces.lookup import get_public_makerspace

    by_slug = Makerspace.objects.create(name="Slug Space", slug="ABCD")
    by_code = Makerspace.objects.create(name="Code Space", slug="code-space")
    by_code.public_code = "ABCD"
    by_code.save(update_fields=["public_code"])

    assert get_public_makerspace("ABCD").pk == by_slug.pk


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def public_makerspace():
    return Makerspace.objects.create(
        name="Public Lab",
        slug="public-lab",
        public_inventory_enabled=True,
    )


def public_inventory_url(makerspace):
    return reverse(
        "public-inventory",
        kwargs={"makerspace_slug": makerspace.slug},
    )


def public_inventory_code_url(makerspace):
    return reverse(
        "public-inventory",
        kwargs={"makerspace_slug": makerspace.public_code},
    )


def signed_headers(path, client_id="web-client", secret="shared-secret", timestamp=None):
    timestamp = timestamp or str(int(timezone.now().timestamp()))
    message = "\n".join(["GET", path, timestamp, ""]).encode()
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return {
        "HTTP_X_CLIENT_ID": client_id,
        "HTTP_X_TIMESTAMP": timestamp,
        "HTTP_X_SIGNATURE": signature,
    }


def create_product(makerspace, name="Soldering Iron", **overrides):
    defaults = {
        "makerspace": makerspace,
        "name": name,
        "description": f"{name} description",
        "is_public": True,
        "is_archived": False,
        "public_availability_mode": PublicAvailabilityMode.STATUS_ONLY,
    }
    defaults.update(overrides)
    return InventoryProduct.objects.create(**defaults)


def public_makerspaces_url():
    return reverse("public-makerspaces")


def get_single_product(api_client, makerspace):
    response = api_client.get(public_inventory_url(makerspace))

    assert response.status_code == 200
    assert set(response.data) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 1

    return response.data["results"][0]


def test_lists_only_public_non_archived_products(api_client, public_makerspace):
    create_product(public_makerspace, name="Public Product")
    create_product(public_makerspace, name="Private Product", is_public=False)
    create_product(public_makerspace, name="Archived Product", is_archived=True)

    response = api_client.get(public_inventory_url(public_makerspace))

    assert response.status_code == 200
    names = [product["name"] for product in response.data["results"]]
    assert names == ["Public Product"]
    assert "Private Product" not in names
    assert "Archived Product" not in names


def test_public_inventory_searches_name_and_description(api_client, public_makerspace):
    create_product(public_makerspace, name="Oscilloscope")
    create_product(
        public_makerspace,
        name="Bench Supply",
        description="Regulated soldering station power supply",
    )
    create_product(public_makerspace, name="Calipers")

    response = api_client.get(public_inventory_url(public_makerspace), {"q": "solder"})

    assert response.status_code == 200
    assert [product["name"] for product in response.data["results"]] == [
        "Bench Supply"
    ]


def test_lists_public_makerspaces(api_client, public_makerspace):
    Makerspace.objects.create(
        name="Private Lab",
        slug="private-lab",
        public_inventory_enabled=False,
    )
    Makerspace.objects.create(
        name="Fab Lab",
        slug="fab-lab",
        location="Building A",
        public_inventory_enabled=True,
    )

    response = api_client.get(public_makerspaces_url())

    assert response.status_code == 200
    assert response.data == [
        {
            "name": "Fab Lab",
            "public_code": response.data[0]["public_code"],
            "slug": "fab-lab",
            "location": "Building A",
        },
        {
            "name": "Public Lab",
            "public_code": public_makerspace.public_code,
            "slug": "public-lab",
            "location": "",
        },
    ]


def test_status_only_mode_hides_exact_count(api_client, public_makerspace):
    create_product(
        public_makerspace,
        public_availability_mode=PublicAvailabilityMode.STATUS_ONLY,
        total_quantity=50,
        available_quantity=50,
    )

    product = get_single_product(api_client, public_makerspace)

    assert product["availability"] == {
        "mode": "status_only",
        "label": "Available",
    }
    assert "count" not in product["availability"]


def test_exact_count_shows_count_when_enabled(api_client, public_makerspace):
    create_product(
        public_makerspace,
        public_availability_mode=PublicAvailabilityMode.EXACT_COUNT,
        show_public_count=True,
        total_quantity=10,
        available_quantity=8,
    )

    product = get_single_product(api_client, public_makerspace)

    assert product["availability"]["mode"] == "exact_count"
    assert product["availability"]["count"] == 8
    assert product["availability"]["label"] == "Available"


def test_exact_count_without_show_count_falls_back_to_status_only(
    api_client,
    public_makerspace,
):
    create_product(
        public_makerspace,
        public_availability_mode=PublicAvailabilityMode.EXACT_COUNT,
        show_public_count=False,
        total_quantity=20,
        available_quantity=2,
    )

    product = get_single_product(api_client, public_makerspace)

    assert product["availability"]["mode"] == "status_only"
    assert "count" not in product["availability"]
    assert product["availability"]["label"] == "Limited"


def test_hidden_mode_returns_null_availability(api_client, public_makerspace):
    create_product(
        public_makerspace,
        public_availability_mode=PublicAvailabilityMode.HIDDEN,
    )

    product = get_single_product(api_client, public_makerspace)

    assert product["availability"] is None


@pytest.mark.parametrize(
    ("total_quantity", "available_quantity", "expected_label"),
    [
        (4, 0, "Unavailable"),
        (15, 3, "Limited"),
        (50, 50, "Available"),
    ],
)
def test_status_labels(
    api_client,
    public_makerspace,
    total_quantity,
    available_quantity,
    expected_label,
):
    create_product(
        public_makerspace,
        public_availability_mode=PublicAvailabilityMode.STATUS_ONLY,
        total_quantity=total_quantity,
        available_quantity=available_quantity,
    )

    product = get_single_product(api_client, public_makerspace)

    assert product["availability"] == {
        "mode": "status_only",
        "label": expected_label,
    }


def test_never_exposes_internal_fields(api_client, public_makerspace):
    create_product(
        public_makerspace,
        storage_location="Locked cabinet A",
        total_quantity=10,
        available_quantity=7,
        reserved_quantity=1,
        issued_quantity=1,
        damaged_quantity=1,
        lost_quantity=0,
        show_public_count=True,
        public_availability_mode=PublicAvailabilityMode.EXACT_COUNT,
    )

    product = get_single_product(api_client, public_makerspace)

    internal_fields = {
        "storage_location",
        "available_quantity",
        "total_quantity",
        "reserved_quantity",
        "issued_quantity",
        "damaged_quantity",
        "lost_quantity",
        "is_public",
        "is_archived",
        "show_public_count",
        "makerspace",
        "makerspace_id",
        "public_availability_mode",
    }
    assert set(product) == PUBLIC_PRODUCT_FIELDS
    assert internal_fields.isdisjoint(product.keys())


def test_unknown_slug_returns_404(api_client):
    response = api_client.get(
        reverse("public-inventory", kwargs={"makerspace_slug": "missing-lab"}),
    )

    assert response.status_code == 404


def test_public_inventory_accepts_public_code(api_client, public_makerspace):
    create_product(public_makerspace, name="Code Product")

    response = api_client.get(public_inventory_code_url(public_makerspace))

    assert response.status_code == 200
    assert response.data["results"][0]["name"] == "Code Product"


def test_public_disabled_returns_404(api_client):
    makerspace = Makerspace.objects.create(
        name="Private Lab",
        slug="private-lab",
        public_inventory_enabled=False,
    )

    response = api_client.get(public_inventory_url(makerspace))

    assert response.status_code == 404


def test_hmac_disabled_by_default(api_client, public_makerspace):
    create_product(public_makerspace)

    response = api_client.get(public_inventory_url(public_makerspace))

    assert response.status_code == 200


def test_hmac_allows_signed_public_inventory_request(
    settings,
    api_client,
    public_makerspace,
):
    # New contract: a registered ApiClient signs with its own secret (Phase 2 Task 16).
    from apps.apiclients.models import ApiClient

    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.HMAC_MAX_CLOCK_SKEW_SECONDS = 300
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/public/"]
    client, secret = ApiClient.issue(label="web", allowed_origins=["http://testserver"])
    create_product(public_makerspace)
    path = public_inventory_url(public_makerspace)

    headers = signed_headers(path, client_id=client.client_id, secret=secret)
    headers["HTTP_ORIGIN"] = "http://testserver"
    response = api_client.get(path, **headers)

    assert response.status_code == 200


def test_frontend_api_client_allows_matching_origin_and_makerspace_code(
    settings,
    api_client,
    public_makerspace,
):
    from apps.apiclients.models import ApiClient

    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/public/"]
    ApiClient.issue(
        label="frontend",
        makerspace=public_makerspace,
        allowed_origins=["https://lab.example.com"],
    )
    client = public_makerspace.api_clients.get()
    create_product(public_makerspace)

    response = api_client.get(
        public_inventory_code_url(public_makerspace),
        HTTP_X_CLIENT_ID=client.client_id,
        HTTP_ORIGIN="https://lab.example.com",
    )

    assert response.status_code == 200


def test_frontend_api_client_rejects_other_makerspace_code(
    settings,
    api_client,
    public_makerspace,
):
    from apps.apiclients.models import ApiClient

    other = Makerspace.objects.create(
        name="Other Lab",
        slug="other-lab",
        public_inventory_enabled=True,
    )
    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/public/"]
    client, _secret = ApiClient.issue(
        label="frontend",
        makerspace=public_makerspace,
        allowed_origins=["https://lab.example.com"],
    )

    response = api_client.get(
        public_inventory_code_url(other),
        HTTP_X_CLIENT_ID=client.client_id,
        HTTP_ORIGIN="https://lab.example.com",
    )

    assert response.status_code == 401


@pytest.mark.parametrize("invalid_signature_case", ["missing", "wrong-client", "wrong-secret"])
def test_hmac_rejects_unsigned_or_invalid_public_inventory_request(
    settings,
    api_client,
    public_makerspace,
    invalid_signature_case,
):
    from apps.apiclients.models import ApiClient

    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.HMAC_MAX_CLOCK_SKEW_SECONDS = 300
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/public/"]
    client, secret = ApiClient.issue(label="web", allowed_origins=["http://testserver"])
    create_product(public_makerspace)
    path = public_inventory_url(public_makerspace)

    headers = {}
    if invalid_signature_case == "wrong-client":
        headers = signed_headers(path, client_id="ck_wrong", secret=secret)
    if invalid_signature_case == "wrong-secret":
        headers = signed_headers(path, client_id=client.client_id, secret="wrong-secret")
    if headers:
        headers["HTTP_ORIGIN"] = "http://testserver"

    response = api_client.get(path, **headers)

    assert response.status_code == 401


def test_openapi_schema_includes_public_inventory_path(api_client):
    response = api_client.get(reverse("schema"))

    assert response.status_code == 200
    schema_text = response.content.decode()
    assert "public/" in schema_text
    assert "inventory" in schema_text


def test_backend_docs_are_not_under_api_prefix(api_client):
    root = api_client.get("/")
    assert root.status_code == 200
    assert b"/docs/" in root.content
    assert b"/redoc/" in root.content
    assert b"window.location.hash" in root.content

    docs = api_client.get("/docs/")
    assert docs.status_code == 200
    assert b"swagger" in docs.content.lower()

    redoc = api_client.get("/redoc/")
    assert redoc.status_code == 200
    assert b"redoc" in redoc.content.lower()

    assert api_client.get("/schema/").status_code == 200
    assert api_client.get("/api/docs/").status_code == 404
    assert api_client.get("/api/schema/").status_code == 404
