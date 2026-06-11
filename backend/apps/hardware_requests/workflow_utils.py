import hashlib

from django.db import IntegrityError

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest


def constraint_name(exc):
    diag = getattr(getattr(exc, "__cause__", None), "diag", None)
    return getattr(diag, "constraint_name", "") or ""


def get_or_create_requester(external_id):
    defaults = {
        "username": requester_username(external_id),
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


def requester_username(external_id):
    digest = hashlib.sha256(external_id.encode()).hexdigest()
    return f"checkin_{digest}"


def locked_request(request):
    # Nullable FKs must not be select_related under SELECT FOR UPDATE in Postgres.
    return (
        HardwareRequest.objects.select_for_update()
        .select_related("makerspace", "requester")
        .get(pk=request.pk)
    )
