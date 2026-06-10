import hashlib

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit import services as audit
from apps.checkin import client as checkin
from apps.hardware_requests import notifications
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.inventory import availability


class InvalidTransition(Exception):
    pass


class RequesterBlocked(Exception):
    pass


class RequestValidationError(Exception):
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
    return (
        HardwareRequest.objects.select_for_update()
        .select_related("makerspace", "requester")
        .get(pk=request.pk)
    )
