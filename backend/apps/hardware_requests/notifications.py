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
