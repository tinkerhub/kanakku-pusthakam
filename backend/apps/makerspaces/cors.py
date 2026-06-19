from corsheaders.signals import check_request_enabled

from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import makerspace_public_origins, makerspace_staff_origins


def origin_is_registered(origin):
    if not origin:
        return False
    for makerspace in Makerspace.objects.filter(archived_at__isnull=True):
        if origin in makerspace_public_origins(makerspace):
            return True
    return False


def staff_origin_is_registered(origin):
    """Credentialed staff-auth endpoints only trust the configured frontend domain."""
    if not origin:
        return False
    for makerspace in Makerspace.objects.filter(
        frontend_domain__isnull=False,
        archived_at__isnull=True,
    ):
        if origin in makerspace_staff_origins(makerspace):
            return True
    return False


def cors_allow_registered_frontend(sender, request, **kwargs):
    origin = request.headers.get("Origin")
    return origin_is_registered(origin)


def register_signal():
    check_request_enabled.connect(cors_allow_registered_frontend)
