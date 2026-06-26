import pytest
from django.db import IntegrityError

from apps.inventory.models import InventoryProduct
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def import_apply_url(makerspace):
    return f"/api/v1/admin/makerspace/{makerspace.id}/inventory/import/apply"


def test_bulk_import_apply_reports_row_integrity_error_and_continues(monkeypatch):
    makerspace = make_space("bulk-hardening-partial")
    admin = make_member("bulk-hardening-partial-admin", makerspace)
    original_get_or_create = InventoryProduct.objects.get_or_create

    def flaky_get_or_create(*args, **kwargs):
        if kwargs.get("name") == "Broken Meter":
            raise IntegrityError("forced inventory conflict")
        return original_get_or_create(*args, **kwargs)

    monkeypatch.setattr(InventoryProduct.objects, "get_or_create", flaky_get_or_create)

    response = authenticated_client(admin).post(
        import_apply_url(makerspace),
        {
            "rows": [
                {"name": "Good Meter", "total_quantity": "2", "available_quantity": "2"},
                {"name": "Broken Meter", "total_quantity": "1", "available_quantity": "1"},
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["applied"] is True
    assert response.data["partial"] is True
    assert response.data["created"] == 1
    assert response.data["updated"] == 0
    assert response.data["summary"]["errors"] == 1
    assert response.data["errors"] == [
        {"row": 3, "errors": {"__all__": "forced inventory conflict"}}
    ]
    assert response.data["rows"][1]["action"] == "error"
    assert InventoryProduct.objects.filter(makerspace=makerspace, name="Good Meter").exists()
    assert not InventoryProduct.objects.filter(makerspace=makerspace, name="Broken Meter").exists()


def test_bulk_import_blank_optional_cells_fall_through_to_defaults():
    # Blank optional cells (reserved/issued buckets, booleans) must use model defaults
    # rather than failing coercion ("Must be an integer") or importing False. Required
    # fields keep their required-error behavior. (Phase 4a review P2.)
    makerspace = make_space("bulk-blank-optional")
    admin = make_member("bulk-blank-optional-admin", makerspace)

    response = authenticated_client(admin).post(
        import_apply_url(makerspace),
        {
            "rows": [
                {
                    "name": "Blank Optionals",
                    "total_quantity": "5",
                    "available_quantity": "5",
                    "reserved_quantity": "",
                    "issued_quantity": "",
                    "is_public": "",
                }
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["summary"]["errors"] == 0
    product = InventoryProduct.objects.get(makerspace=makerspace, name="Blank Optionals")
    assert product.reserved_quantity == 0
    assert product.issued_quantity == 0
    assert product.is_public is True


def test_bulk_import_apply_skips_invalid_preview_rows_and_continues():
    makerspace = make_space("bulk-hardening-invalid")
    admin = make_member("bulk-hardening-invalid-admin", makerspace)

    response = authenticated_client(admin).post(
        import_apply_url(makerspace),
        {
            "rows": [
                {"name": "Good Meter", "total_quantity": "2", "available_quantity": "2"},
                {"name": "Bad Meter", "total_quantity": "1", "available_quantity": "2"},
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["applied"] is True
    assert response.data["partial"] is True
    assert response.data["valid"] is False
    assert response.data["created"] == 1
    assert response.data["summary"]["errors"] == 1
    assert response.data["rows"][1]["action"] == "error"
    assert InventoryProduct.objects.filter(makerspace=makerspace, name="Good Meter").exists()
    assert not InventoryProduct.objects.filter(makerspace=makerspace, name="Bad Meter").exists()


def test_bulk_import_apply_happy_path_still_creates_all_rows():
    makerspace = make_space("bulk-hardening-happy")
    admin = make_member("bulk-hardening-happy-admin", makerspace)

    response = authenticated_client(admin).post(
        import_apply_url(makerspace),
        {
            "rows": [
                {"name": "Calipers", "total_quantity": "2", "available_quantity": "2"},
                {"name": "Scope", "total_quantity": "1", "available_quantity": "1"},
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["applied"] is True
    assert response.data["partial"] is False
    assert response.data["created"] == 2
    assert response.data["updated"] == 0
    assert InventoryProduct.objects.filter(makerspace=makerspace).count() == 2
