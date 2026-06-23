"""Phase 1 (security/PII): reports carry readable borrower identities now, so they
are VIEW_AUDIT-gated. Guest Admins (handout-only) must not read or export them, and
exported requester labels must be neutralized against spreadsheet formula injection."""

import pytest
from django.urls import reverse

from apps.makerspaces.models import MakerspaceMembership
from apps.operations import views_reports
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def _guest(makerspace):
    return make_member(
        "guest-reports",
        makerspace,
        membership_role=MakerspaceMembership.Role.GUEST_ADMIN,
    )


def _inventory_manager(makerspace):
    return make_member(
        "inv-reports",
        makerspace,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
    )


def test_guest_admin_cannot_read_reports():
    makerspace = make_space("reports-guest-read")
    url = reverse("analytics-active-loans", kwargs={"makerspace_id": makerspace.id})
    response = authenticated_client(_guest(makerspace)).get(url)
    assert response.status_code in (403, 404)


def test_guest_admin_cannot_export_reports():
    makerspace = make_space("reports-guest-export")
    url = reverse(
        "report-export",
        kwargs={"makerspace_id": makerspace.id, "report_key": "active-loans"},
    )
    response = authenticated_client(_guest(makerspace)).get(url)
    assert response.status_code in (403, 404)


def test_inventory_manager_can_read_reports():
    makerspace = make_space("reports-inv-read")
    url = reverse("analytics-active-loans", kwargs={"makerspace_id": makerspace.id})
    response = authenticated_client(_inventory_manager(makerspace)).get(url)
    assert response.status_code == 200


def test_csv_export_neutralizes_formula_injection():
    rows = [["holder", "requests"], ["=HYPERLINK(\"http://evil\")", 2], ["+1", 1], ["safe", 3]]
    response = views_reports._csv_response(rows, "active-loans.csv")
    body = response.content.decode()
    assert "'=HYPERLINK" in body
    assert "'+1" in body
    # A benign label is untouched (no spurious apostrophe).
    assert "\nsafe,3" in body or "safe,3" in body


def test_xlsx_cell_neutralizes_formula_injection():
    assert views_reports._xlsx_cell("=cmd|'/c calc'") == "'=cmd|'/c calc'"
    assert views_reports._xlsx_cell("normal") == "normal"


def test_email_log_admin_never_exposes_bodies():
    from apps.integrations.admin_email_logs import EmailLogAdmin

    # Bodies can carry PII / live recovery tokens — never rendered in /control/.
    assert "text_body" not in EmailLogAdmin.fields
    assert "html_body" not in EmailLogAdmin.fields
    assert "text_body" not in EmailLogAdmin.readonly_fields
    assert "html_body" not in EmailLogAdmin.readonly_fields


def test_ledger_holder_falls_back_to_member_for_hash_only_requester():
    from types import SimpleNamespace

    from apps.operations.ledger import _request_holder

    request = SimpleNamespace(
        requester=None,
        requester_contact_email="",
        requester_contact_phone="",
        requester_username="checkin_" + "a" * 64,
    )
    # The internal privacy hash must never surface as a holder label.
    assert _request_holder(request) == "Member"
