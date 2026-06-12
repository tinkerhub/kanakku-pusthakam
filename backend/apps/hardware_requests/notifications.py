import logging

from apps.integrations.email import send_makerspace_email
from apps.integrations.telegram import TelegramDeliveryError, send_message

logger = logging.getLogger(__name__)


def notify_request_submitted(request):
    """Telegram integration point for submitted hardware requests."""
    logger.info(
        "Hardware request submitted.",
        extra={
            "request_id": request.pk,
            "makerspace_id": request.makerspace_id,
            "status": request.status,
        },
    )
    _send_request_message(
        request,
        f"New hardware request #{request.pk} from {request.requester_username}.",
    )
    _send_request_confirmation(request)


def notify_request_accepted(request):
    logger.info(
        "Hardware request accepted.",
        extra={
            "request_id": request.pk,
            "makerspace_id": request.makerspace_id,
            "status": request.status,
        },
    )
    _send_status_email(
        request,
        "request approved",
        "Your makerspace request has been approved.",
    )


def notify_request_rejected(request):
    logger.info(
        "Hardware request rejected.",
        extra={
            "request_id": request.pk,
            "makerspace_id": request.makerspace_id,
            "status": request.status,
        },
    )
    body = "Your makerspace request was rejected."
    if request.rejection_reason:
        body = f"{body}\n\nReason: {request.rejection_reason}"
    _send_status_email(request, "request rejected", body)


def notify_request_issued(request):
    """Telegram integration point for issued hardware requests."""
    logger.info(
        "Hardware request issued.",
        extra={
            "request_id": request.pk,
            "makerspace_id": request.makerspace_id,
            "status": request.status,
        },
    )
    _send_request_message(request, f"Hardware request #{request.pk} has been issued.")
    _send_status_email(
        request,
        "request issued",
        "Your approved makerspace request has been handed out.",
    )


def notify_request_returned(request):
    """Telegram integration point for returned hardware requests."""
    logger.info(
        "Hardware request returned.",
        extra={
            "request_id": request.pk,
            "makerspace_id": request.makerspace_id,
            "status": request.status,
        },
    )
    _send_request_message(request, f"Hardware request #{request.pk} has been returned.")
    _send_status_email(
        request,
        "request returned",
        "Your makerspace request has been returned and closed.",
    )


def _send_request_message(request, text):
    reply_markup = None
    if request.status == request.Status.PENDING_APPROVAL:
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "Accept", "callback_data": f"accept:{request.pk}"},
                    {
                        "text": "Reject",
                        "callback_data": f"reject:{request.pk}:Rejected from Telegram.",
                    },
                ]
            ]
        }
    try:
        send_message(request.makerspace, text, reply_markup=reply_markup)
    except TelegramDeliveryError:
        logger.exception(
            "Telegram request notification failed.",
            extra={"request_id": request.pk},
        )


def _send_request_confirmation(request):
    body = (
        f"Your makerspace request #{request.pk} was received.\n\n"
        f"Status: {request.status}\n"
        "Use your email or phone on the public request page to check status."
    )
    _send_status_email(request, "request received", body)


def _send_status_email(request, subject_suffix, body):
    recipient = request.requester_contact_email
    if not recipient:
        return

    subject = f"{request.makerspace.name} {subject_suffix}"
    try:
        send_makerspace_email(request.makerspace, subject, body, [recipient])
    except Exception:
        logger.warning(
            "request_status_email_failed",
            extra={"request_id": request.pk, "recipient": recipient},
            exc_info=True,
        )
