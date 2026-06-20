import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.makerspaces.models import Makerspace, MakerspaceMembership

pytestmark = pytest.mark.django_db


def test_seed_demo_creates_three_spaces_staff_and_inventory():
    call_command("seed_demo", password="same-pass-123")

    spaces = {space.slug: space for space in Makerspace.objects.all()}
    assert set(spaces) == {"calicut", "kochi", "trivandrum"}
    assert spaces["calicut"].name == "TinkerSpace Calicut"
    assert spaces["kochi"].name == "TinkerSpace Kochi"
    assert spaces["trivandrum"].name == "TinkerSpace Trivandrum"
    assert spaces["kochi"].superadmin_access_enabled is False
    assert spaces["kochi"].location == "North Wing - Woodshop"

    for username in ("superadmin", "alpha_manager", "beta_manager", "gamma_manager"):
        assert User.objects.get(username=username).check_password("same-pass-123")

    assert MakerspaceMembership.objects.filter(
        makerspace=spaces["kochi"],
        role=MakerspaceMembership.Role.SPACE_MANAGER,
    ).exists()
    assert InventoryProduct.objects.count() == 15
    assert InventoryAsset.objects.count() == 9
