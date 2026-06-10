import logging

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
