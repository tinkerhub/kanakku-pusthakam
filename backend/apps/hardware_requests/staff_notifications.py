import logging

from django.template import Context, Template
from django.utils import timezone

from apps.hardware_requests.models import HardwareRequest
from apps.integrations.email import send_makerspace_email
from apps.integrations.staff_notifications import staff_emails_for_stream

logger = logging.getLogger(__name__)

STAFF_TEMPLATES = {
    "submitted": {
        "subject": "{{ makerspace.name }} hardware request #{{ request.id }} submitted",
        "text_body": "A new hardware request needs review.\n\n{{ staff_summary }}",
    },
    "accepted": {
        "subject": "{{ makerspace.name }} hardware request #{{ request.id }} accepted",
        "text_body": "Hardware request #{{ request.id }} was accepted.\n\n{{ staff_summary }}",
    },
    "rejected": {
        "subject": "{{ makerspace.name }} hardware request #{{ request.id }} rejected",
        "text_body": "Hardware request #{{ request.id }} was rejected.\n\n{{ staff_summary }}",
    },
    "issued": {
        "subject": "{{ makerspace.name }} hardware request #{{ request.id }} issued",
        "text_body": "Hardware request #{{ request.id }} was issued.\n\n{{ staff_summary }}",
    },
    "partially_returned": {
        "subject": "{{ makerspace.name }} hardware request #{{ request.id }} partially returned",
        "text_body": "Hardware request #{{ request.id }} was partially returned.\n\n{{ staff_summary }}",
    },
    "returned": {
        "subject": "{{ makerspace.name }} hardware request #{{ request.id }} returned",
        "text_body": "Hardware request #{{ request.id }} was fully returned and closed.\n\n{{ staff_summary }}",
    },
    "closed_with_issue": {
        "subject": "{{ makerspace.name }} hardware request #{{ request.id }} closed with issue",
        "text_body": "Hardware request #{{ request.id }} was closed with damaged or missing items.\n\n{{ staff_summary }}",
    },
    "return_reminder": {
        "subject": "{{ makerspace.name }} hardware request #{{ request.id }} return reminder",
        "text_body": "Hardware request #{{ request.id }} is due for return.\n\n{{ staff_summary }}",
    },
}


def send_staff_hardware_email(request, event) -> bool:
    """Send the staff-facing hardware notification. Returns True iff at least one staff
    email was actually delivered (used by notify_return_due to avoid re-sending the staff
    reminder on every cron run when the borrower has no reachable email)."""
    try:
        staff_request = (
            HardwareRequest.objects.select_related(
                "makerspace",
                "requester",
                "assigned_box",
            )
            .prefetch_related("items__product")
            .get(pk=request.pk)
        )
        recipients = staff_emails_for_stream(staff_request.makerspace, "hardware")
        if not recipients:
            return False

        template = STAFF_TEMPLATES[event]
        context = Context(
            {
                "request": staff_request,
                "makerspace": staff_request.makerspace,
                "staff_summary": _staff_summary(staff_request),
                "now": timezone.now(),
            },
            autoescape=True,
        )
        subject = Template(template["subject"]).render(context).strip()
        body = Template(template["text_body"]).render(context)
        return bool(send_makerspace_email(staff_request.makerspace, subject, body, recipients))
    except Exception:
        logger.warning(
            "hardware_staff_notification_failed",
            extra={
                "request_id": getattr(request, "pk", None),
                "event": event,
            },
            exc_info=True,
        )
        return False


def _staff_summary(request):
    lines = [
        f"Status: {request.status}",
        f"Requester: {request.requester_username or 'Unknown requester'}",
    ]
    if request.requester_contact_email:
        lines.append(f"Email: {request.requester_contact_email}")
    if request.requester_contact_phone:
        lines.append(f"Phone: {request.requester_contact_phone}")
    if request.assigned_box_id:
        lines.append(f"Box: {request.assigned_box.code}")
    if request.return_due_at:
        lines.append(f"Return due: {request.return_due_at}")
    if request.rejection_reason:
        lines.append(f"Reason: {request.rejection_reason}")
    return "\n".join(lines)
