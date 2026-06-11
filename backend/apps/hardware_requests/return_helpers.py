from django.utils import timezone

from apps.audit import services as audit
from apps.hardware_requests.models import HardwareRequest, RequesterAccountability
from apps.hardware_requests.workflow_errors import ReturnValidationError


def build_resolutions(locked, resolutions):
    item_ids = [resolution["item_id"] for resolution in resolutions]
    items = {
        item.pk: item
        for item in locked.items.select_related("product").filter(pk__in=item_ids)
    }
    validated = []
    total_resolved = 0
    for resolution in resolutions:
        item = items.get(resolution["item_id"])
        if item is None:
            raise ReturnValidationError("Return item does not belong to this loan.")

        returned = resolution["returned"]
        damaged = resolution["damaged"]
        missing = resolution["missing"]
        if returned < 0 or damaged < 0 or missing < 0:
            raise ReturnValidationError("Return quantities cannot be negative.")

        quantity = returned + damaged + missing
        if quantity > remaining_quantity(item):
            raise ReturnValidationError(
                "Return quantity exceeds remaining issued quantity."
            )

        total_resolved += quantity
        validated.append(
            {
                "item": item,
                "returned": returned,
                "damaged": damaged,
                "missing": missing,
            }
        )

    if total_resolved < 1:
        raise ReturnValidationError("At least one item must be resolved.")
    return validated


def remaining_quantity(item):
    return item.issued_quantity - (
        item.returned_quantity + item.damaged_quantity + item.missing_quantity
    )


def write_accountability(actor, locked, evidence, resolutions):
    for resolution in resolutions:
        item = resolution["item"]
        _write_issue(
            actor,
            locked,
            item,
            evidence,
            RequesterAccountability.IssueType.DAMAGED,
            resolution["damaged"],
        )
        _write_issue(
            actor,
            locked,
            item,
            evidence,
            RequesterAccountability.IssueType.MISSING,
            resolution["missing"],
        )


def finalize_return_status(locked, actor):
    all_items = list(locked.items.all())
    all_resolved = all(
        (
            item.returned_quantity + item.damaged_quantity + item.missing_quantity
        )
        == item.issued_quantity
        for item in all_items
    )
    has_issue = any(
        item.damaged_quantity > 0 or item.missing_quantity > 0 for item in all_items
    )

    if not all_resolved:
        locked.status = HardwareRequest.Status.PARTIALLY_RETURNED
        locked.save(update_fields=["status", "updated_at"])
        return "request.partially_returned"

    locked.status = (
        HardwareRequest.Status.CLOSED_WITH_ISSUE
        if has_issue
        else HardwareRequest.Status.RETURNED
    )
    locked.closed_by = actor
    locked.closed_at = timezone.now()
    locked.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    if has_issue:
        return "request.closed_with_issue"
    return "request.returned"


def _write_issue(actor, locked, item, evidence, issue_type, quantity):
    if quantity <= 0:
        return

    RequesterAccountability.objects.create(
        requester=locked.requester,
        request=locked,
        request_item=item,
        makerspace=locked.makerspace,
        issue_type=issue_type,
        evidence_photo=evidence,
        quantity=quantity,
        created_by=actor,
    )
    audit.record(
        actor,
        f"item.{issue_type}",
        makerspace=locked.makerspace,
        target=item,
        meta={
            "request_id": locked.pk,
            "evidence_id": evidence.pk,
            "quantity": quantity,
        },
    )
