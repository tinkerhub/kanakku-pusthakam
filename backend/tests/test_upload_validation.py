import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.inventory import public_image_storage
from tests.return_helpers import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db


def image_url(product):
    return reverse("admin-inventory-image", kwargs={"pk": product.id})


@pytest.mark.parametrize(
    "object_key",
    [
        "../items/1/photo.png",
        "/items/1/photo.png",
        "items\\1\\photo.png",
        "items/1/bad\x1f.png",
        "items/1/bad\x7f.png",
    ],
)
def test_public_image_object_key_rejects_unsafe_paths(object_key):
    assert not public_image_storage.is_safe_object_key(object_key)


def test_public_image_attach_rejects_non_image_bytes(monkeypatch):
    makerspace = make_space("upload-validation-invalid")
    user = make_member("upload-validation-invalid-user", makerspace)
    product = make_product(makerspace)
    object_key = f"items/{makerspace.id}/not-image.png"
    deleted = []

    monkeypatch.setattr(
        public_image_storage,
        "finalize_upload",
        lambda key: public_image_storage.FinalizeResult("ok", 123),
    )
    monkeypatch.setattr(public_image_storage, "sniff_is_valid_image", lambda key: False)
    monkeypatch.setattr(public_image_storage, "delete_object", lambda key: deleted.append(key))

    response = authenticated_client(user).put(
        image_url(product),
        {"object_key": object_key},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["object_key"] == "Uploaded file is not a valid image."
    product.refresh_from_db()
    assert product.image_key == ""
    assert deleted == [object_key, public_image_storage.staging_key(object_key)]
    assert AuditLog.objects.count() == 0


def test_public_image_attach_accepts_valid_image_bytes(monkeypatch):
    makerspace = make_space("upload-validation-valid")
    user = make_member("upload-validation-valid-user", makerspace)
    product = make_product(makerspace)
    object_key = f"items/{makerspace.id}/valid.png"
    deleted = []

    monkeypatch.setattr(
        public_image_storage,
        "finalize_upload",
        lambda key: public_image_storage.FinalizeResult("ok", 123),
    )
    monkeypatch.setattr(public_image_storage, "sniff_is_valid_image", lambda key: True)
    monkeypatch.setattr(public_image_storage, "delete_object", lambda key: deleted.append(key))

    response = authenticated_client(user).put(
        image_url(product),
        {"object_key": object_key},
        format="json",
    )

    assert response.status_code == 200
    product.refresh_from_db()
    assert product.image_key == object_key
    assert deleted == []
    assert AuditLog.objects.filter(action="inventory.image_attached").exists()
