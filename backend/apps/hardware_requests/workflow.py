import hashlib

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit import services as audit
from apps.boxes.models import Box, BoxScan
from apps.checkin import client as checkin
from apps.evidence import storage
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests import notifications
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.inventory import availability


class InvalidTransition(Exception):
    pass


class RequesterBlocked(Exception):
    pass


class RequestValidationError(Exception):
    pass


class BoxValidationError(Exception):
    """Bad box input (unknown/inactive box code) — maps to 400."""


class BoxUnavailable(Exception):
    """Box is already out on another active loan — a state conflict, maps to 409."""


class EvidenceNotUploaded(Exception):
    pass


def submit_request(makerspace, identifier, items, requested_for=""):
    result = checkin.verify(makerspace, identifier)

    with transaction.atomic():
        requester = _get_or_create_requester(result.external_id)
        if requester.access_status != User.AccessStatus.ACTIVE:
            raise RequesterBlocked("Requester is not active.")

        request = HardwareRequest.objects.create(
            makerspace=makerspace,
            requester=requester,
            requester_username=result.username,
            status=HardwareRequest.Status.PENDING_APPROVAL,
            requested_for=requested_for,
        )
        HardwareRequestItem.objects.bulk_create(
            [
                HardwareRequestItem(
                    request=request,
                    product=item["product"],
                    requested_quantity=item["quantity"],
                )
                for item in items
            ]
        )
        audit.record(
            requester,
            "request.submitted",
            makerspace=makerspace,
            target=request,
        )
        transaction.on_commit(lambda: notifications.notify_request_submitted(request))
        return request


def accept_request(actor, request):
    with transaction.atomic():
        locked = _locked_request(request)
        if locked.status != HardwareRequest.Status.PENDING_APPROVAL:
            raise InvalidTransition(
                f"Cannot accept hardware request with status {locked.status}."
            )

        items = list(locked.items.order_by("product_id"))
        for item in items:
            item.accepted_quantity = item.requested_quantity
            item.save(update_fields=["accepted_quantity"])

        availability.reserve_for_request(locked)

        locked.status = HardwareRequest.Status.ACCEPTED
        locked.accepted_by = actor
        locked.accepted_at = timezone.now()
        locked.save(
            update_fields=[
                "status",
                "accepted_by",
                "accepted_at",
                "updated_at",
            ]
        )
        audit.record(
            actor,
            "request.accepted",
            makerspace=locked.makerspace,
            target=locked,
        )
        return locked


def assign_box(actor, request, box_code):
    with transaction.atomic():
        locked = _locked_request(request)
        if locked.status != HardwareRequest.Status.ACCEPTED:
            raise InvalidTransition(
                f"Cannot assign box for hardware request with status {locked.status}."
            )

        box = Box.objects.filter(
            makerspace=locked.makerspace,
            code=box_code,
            is_active=True,
        ).first()
        if box is None:
            raise BoxValidationError("Unknown or inactive box.")

        occupied = HardwareRequest.objects.filter(
            assigned_box=box,
            status__in=[
                HardwareRequest.Status.ISSUED,
                HardwareRequest.Status.PARTIALLY_RETURNED,
            ],
        ).exclude(pk=locked.pk)
        if occupied.exists():
            raise BoxUnavailable("Box is already out on another loan.")

        locked.assigned_box = box
        locked.save(update_fields=["assigned_box", "updated_at"])
        scan = BoxScan.objects.create(
            makerspace=locked.makerspace,
            box=box,
            request=locked,
            actor=actor,
            context=BoxScan.Context.ISSUE,
        )
        audit.record(
            actor,
            "box.assigned",
            makerspace=locked.makerspace,
            target=locked,
            meta={"box_id": box.pk},
        )
        audit.record(
            actor,
            "box.scanned",
            makerspace=locked.makerspace,
            target=scan,
            meta={"box_id": box.pk, "request_id": locked.pk},
        )
        return locked


def issue_request(actor, request, evidence_id, remark=""):
    evidence = EvidencePhoto.objects.filter(
        pk=evidence_id,
        makerspace_id=request.makerspace_id,
        evidence_type=EvidencePhoto.EvidenceType.ISSUE,
    ).first()
    if evidence is None:
        raise RequestValidationError("Invalid issue evidence.")
    if not storage.object_exists(evidence.object_key):
        raise EvidenceNotUploaded("Issue evidence has not been uploaded.")

    with transaction.atomic():
        locked = _locked_request(request)
        if locked.status != HardwareRequest.Status.ACCEPTED:
            raise InvalidTransition(
                f"Cannot issue hardware request with status {locked.status}."
            )
        if not locked.assigned_box_id or not BoxScan.objects.filter(
            request=locked,
            box_id=locked.assigned_box_id,
            context=BoxScan.Context.ISSUE,
        ).exists():
            raise RequestValidationError("Box scan required before issue.")

        availability.issue_items(locked)

        locked.issue_evidence = evidence
        locked.issue_remark = remark
        locked.issued_by = actor
        locked.issued_at = timezone.now()
        locked.status = HardwareRequest.Status.ISSUED
        try:
            locked.save(
                update_fields=[
                    "issue_evidence",
                    "issue_remark",
                    "issued_by",
                    "issued_at",
                    "status",
                    "updated_at",
                ]
            )
        except IntegrityError as exc:
            constraint = _constraint_name(exc)
            if constraint == "uniq_active_loan_per_box":
                raise BoxUnavailable("Box is already out on another loan.") from exc
            if constraint and "issue_evidence" in constraint:
                raise RequestValidationError("Evidence already used.") from exc
            raise InvalidTransition("Could not issue request due to a conflict.") from exc

        audit.record(
            actor,
            "evidence.attached",
            makerspace=locked.makerspace,
            target=evidence,
            meta={"request_id": locked.pk},
        )
        audit.record(
            actor,
            "request.issued",
            makerspace=locked.makerspace,
            target=locked,
            meta={"box_id": locked.assigned_box_id, "evidence_id": evidence.pk},
        )
        transaction.on_commit(
            lambda request_id=locked.pk: notifications.notify_request_issued(
                HardwareRequest.objects.select_related(
                    "makerspace",
                    "requester",
                    "issued_by",
                    "assigned_box",
                ).get(pk=request_id)
            )
        )
        return locked


def reject_request(actor, request, reason):
    reason = str(reason or "").strip()
    if not reason:
        raise RequestValidationError("Rejection reason is required.")

    with transaction.atomic():
        locked = _locked_request(request)
        if locked.status != HardwareRequest.Status.PENDING_APPROVAL:
            raise InvalidTransition(
                f"Cannot reject hardware request with status {locked.status}."
            )

        locked.status = HardwareRequest.Status.REJECTED
        locked.rejection_reason = reason
        locked.save(
            update_fields=[
                "status",
                "rejection_reason",
                "updated_at",
            ]
        )
        audit.record(
            actor,
            "request.rejected",
            makerspace=locked.makerspace,
            target=locked,
            meta={"reason": reason},
        )
        return locked


def _constraint_name(exc):
    diag = getattr(getattr(exc, "__cause__", None), "diag", None)
    return getattr(diag, "constraint_name", "") or ""


def _get_or_create_requester(external_id):
    defaults = {
        "username": _requester_username(external_id),
        "role": User.Role.REQUESTER,
        "access_status": User.AccessStatus.ACTIVE,
        "is_active": True,
    }
    try:
        requester, _ = User.objects.get_or_create(
            external_checkin_user_id=external_id,
            defaults=defaults,
        )
        return requester
    except IntegrityError:
        return User.objects.get(external_checkin_user_id=external_id)


def _requester_username(external_id):
    # Full 64-char hex digest (fits User.username max_length=150): a function of the
    # unique external id, so it is 1:1 with it and collision-proof in practice. Validator-
    # clean (hex only). Keep the full digest — truncating reintroduces collision risk.
    digest = hashlib.sha256(external_id.encode()).hexdigest()
    return f"checkin_{digest}"


def _locked_request(request):
    # Only non-null FKs may be select_related here: Postgres rejects SELECT ... FOR
    # UPDATE across the nullable side of an outer join, so `assigned_box` (nullable)
    # must NOT be joined. issue_request only needs `assigned_box_id`, not the row.
    return (
        HardwareRequest.objects.select_for_update()
        .select_related("makerspace", "requester")
        .get(pk=request.pk)
    )
