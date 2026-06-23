"""Phase 2 (correctness / data integrity) regression tests for the review fixes:
purge cleans up email rows, dispatch fails closed on redacted-async, the top-borrowers
leaderboard doesn't fragment a borrower, and a printer's image is dropped on move."""

import pytest

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.integrations.dispatch import dispatch_email
from apps.integrations.models import EmailLog, EmailNotificationMute
from apps.inventory import public_image_storage
from apps.makerspaces import lifecycle
from apps.operations import reports
from apps.printing.models import PrintPrinter
from apps.printing.serializers_printers import PrintPrinterSerializer
from tests.return_helpers import make_member, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def _superadmin(username):
    return make_user(username, role=User.Role.SUPERADMIN, is_staff=True, is_superuser=True)


def test_purge_deletes_email_logs_and_mutes():
    makerspace = make_space("purge-email-rows")
    actor = _superadmin("purge-email-super")
    EmailLog.objects.create(makerspace=makerspace, to_email="a@b.com", subject="hi")
    EmailNotificationMute.objects.create(
        makerspace=makerspace,
        target="requester",
        stream="hardware",
        event="request_accepted",
        audience="requester",
    )
    makerspace = lifecycle.archive(makerspace, actor)
    lifecycle.purge(makerspace, actor)
    assert not EmailLog.objects.filter(makerspace_id=makerspace.id).exists()
    assert not EmailNotificationMute.objects.filter(makerspace_id=makerspace.id).exists()


def test_dispatch_email_rejects_redacted_async():
    # A redacted (persist_body=False) row reloaded by the worker has no body, so async
    # would deliver blank mail. dispatch_email must fail closed instead.
    with pytest.raises(ValueError):
        dispatch_email(
            to_email="x@y.com",
            subject="s",
            text_body="body",
            persist_body=False,
            sync=False,
        )


def test_top_borrowers_does_not_fragment_same_requester_with_changed_username():
    makerspace = make_space("top-borrowers-no-frag")
    actor = make_member("frag-mgr", makerspace)
    product = make_product(makerspace, name="Saw", total_quantity=20, available_quantity=20)
    requester = make_user(
        "frag-requester",
        access_status=User.AccessStatus.ACTIVE,
        external_checkin_user_id="frag@member.com",
    )
    # Same requester, two issued requests with DIFFERENT per-request username snapshots.
    for snapshot in ("old-label", "new-label"):
        request = HardwareRequest.objects.create(
            makerspace=makerspace,
            requester=requester,
            requester_username=snapshot,
            status=HardwareRequest.Status.ISSUED,
            issued_by=actor,
        )
        HardwareRequestItem.objects.create(
            request=request,
            product=product,
            requested_quantity=1,
            accepted_quantity=1,
            issued_quantity=1,
        )
    rows = reports._top_borrowers(makerspace.id, aggregate=False)
    # header + exactly ONE merged data row (not fragmented into two).
    assert len(rows) == 2
    assert rows[1][1] == 2  # requests merged
    assert rows[1][2] == 2  # items_borrowed merged


def test_printer_image_dropped_on_makerspace_move(monkeypatch):
    source = make_space("printer-move-src")
    destination = make_space("printer-move-dst")
    printer = PrintPrinter.objects.create(
        makerspace=source,
        name="P1",
        image_key=f"printers/{source.id}/x.jpg",
    )
    deleted = []
    monkeypatch.setattr(public_image_storage, "delete_object", lambda key: deleted.append(key))

    serializer = PrintPrinterSerializer(
        instance=printer,
        data={"makerspace": destination.id, "name": "P1"},
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    printer.refresh_from_db()

    assert printer.makerspace_id == destination.id
    assert printer.image_key == ""
    assert deleted == [f"printers/{source.id}/x.jpg"]
