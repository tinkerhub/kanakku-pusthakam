from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.inventory.serializers import PublicMakerspaceSerializer
from apps.makerspaces.platform import bootstrap_payload
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def admin_makerspace_url(makerspace):
    return f"/api/v1/admin/makerspaces/{makerspace.id}"


def test_makerspace_latitude_without_longitude_is_rejected():
    makerspace = make_space("geo-set-one")
    manager = make_member("geo-set-one-manager", makerspace)

    response = authenticated_client(manager).patch(
        admin_makerspace_url(makerspace),
        {"latitude": "12.345678"},
        format="json",
    )

    assert response.status_code == 400
    assert "latitude" in response.data


def test_makerspace_clearing_one_coordinate_is_rejected():
    makerspace = make_space("geo-clear-one")
    makerspace.latitude = Decimal("12.345678")
    makerspace.longitude = Decimal("77.123456")
    makerspace.save(update_fields=["latitude", "longitude", "updated_at"])
    manager = make_member("geo-clear-one-manager", makerspace)

    response = authenticated_client(manager).patch(
        admin_makerspace_url(makerspace),
        {"latitude": None},
        format="json",
    )

    assert response.status_code == 400
    assert "latitude" in response.data


def test_makerspace_setting_both_coordinates_succeeds():
    makerspace = make_space("geo-set-both")
    manager = make_member("geo-set-both-manager", makerspace)

    response = authenticated_client(manager).patch(
        admin_makerspace_url(makerspace),
        {"latitude": "12.345678", "longitude": "77.123456"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["latitude"] == "12.345678"
    assert response.data["longitude"] == "77.123456"
    assert (
        response.data["map_url"]
        == "https://www.google.com/maps?q=12.345678,77.123456"
    )
    makerspace.refresh_from_db()
    assert makerspace.latitude == Decimal("12.345678")
    assert makerspace.longitude == Decimal("77.123456")


def test_makerspace_clearing_both_coordinates_succeeds():
    makerspace = make_space("geo-clear-both")
    makerspace.latitude = Decimal("12.345678")
    makerspace.longitude = Decimal("77.123456")
    makerspace.save(update_fields=["latitude", "longitude", "updated_at"])
    manager = make_member("geo-clear-both-manager", makerspace)

    response = authenticated_client(manager).patch(
        admin_makerspace_url(makerspace),
        {"latitude": None, "longitude": None},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["latitude"] is None
    assert response.data["longitude"] is None
    assert response.data["map_url"] == ""
    makerspace.refresh_from_db()
    assert makerspace.latitude is None
    assert makerspace.longitude is None


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"latitude": "91.000000", "longitude": "77.123456"}, "latitude"),
        ({"latitude": "12.345678", "longitude": "181.000000"}, "longitude"),
        ({"latitude": "12.3456789", "longitude": "77.123456"}, "latitude"),
    ],
)
def test_makerspace_coordinate_validation_rejects_invalid_values(payload, field):
    makerspace = make_space(f"geo-invalid-{field}-{payload[field].replace('.', '-')}")
    manager = make_member(f"geo-invalid-{field}-{makerspace.id}", makerspace)

    response = authenticated_client(manager).patch(
        admin_makerspace_url(makerspace),
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert field in response.data


def test_makerspace_map_url_property_uses_coordinates_when_present():
    makerspace = make_space("geo-property")

    assert makerspace.map_url == ""

    makerspace.latitude = Decimal("12.345678")
    makerspace.longitude = Decimal("77.123456")

    assert (
        makerspace.map_url
        == "https://www.google.com/maps?q=12.345678,77.123456"
    )


def test_public_makerspace_serializer_and_bootstrap_expose_map_url():
    makerspace = make_space("geo-public")
    makerspace.location = "TinkerSpace"
    makerspace.latitude = Decimal("12.345678")
    makerspace.longitude = Decimal("77.123456")
    makerspace.save(update_fields=["location", "latitude", "longitude", "updated_at"])

    serializer_data = PublicMakerspaceSerializer(makerspace).data
    bootstrap_data = bootstrap_payload(makerspace)
    list_response = APIClient().get("/api/v1/public/makerspaces/")

    expected = "https://www.google.com/maps?q=12.345678,77.123456"
    assert serializer_data["location"] == "TinkerSpace"
    assert serializer_data["map_url"] == expected
    assert bootstrap_data["makerspace"]["map_url"] == expected
    assert list_response.status_code == 200
    listed = next(row for row in list_response.data if row["slug"] == makerspace.slug)
    assert listed["map_url"] == expected
