import logging

from apps.integrations.email_registry_hardware import HARDWARE_TEMPLATES
from apps.integrations.email_registry_printing import PRINTING_TEMPLATES
from apps.integrations.models import EmailNotificationMute
from apps.makerspaces.models import MakerspaceMembership

logger = logging.getLogger(__name__)

# return_reminder is never mutable in any (stream, audience): the overdue-loan
# reminder is an accountability email, not a courtesy notification.
ALWAYS_ON = frozenset({"return_reminder"})


def _events(templates, family, audience, prefix):
    # Our registry keys are PREFIXED (hw_/hw_staff_/print_/print_staff_); the send
    # sites + mute rows use BARE event names (the registry key minus its prefix —
    # e.g. send_print_email builds "print_" + event). Strip the per-audience prefix
    # so the catalog's bare names match exactly what the send sites pass to the
    # mute checks. Filter by family+audience first so a staff key is never matched
    # by the requester prefix (e.g. "hw_staff_*" is excluded from the "hw_" pass).
    events = []
    for key, entry in templates.items():
        if entry["family"] != family or entry["audience"] != audience:
            continue
        if not key.startswith(prefix):
            continue
        event = key[len(prefix):]
        if event not in ALWAYS_ON:
            events.append(event)
    return tuple(events)


EVENT_CATALOG = {
    ("hardware", "requester"): _events(HARDWARE_TEMPLATES, "hardware", "requester", "hw_"),
    ("hardware", "staff"): _events(HARDWARE_TEMPLATES, "hardware", "staff", "hw_staff_"),
    ("printing", "requester"): _events(PRINTING_TEMPLATES, "printing", "requester", "print_"),
    ("printing", "staff"): _events(PRINTING_TEMPLATES, "printing", "staff", "print_staff_"),
}

TARGETS = {
    MakerspaceMembership.Role.SPACE_MANAGER.value: "staff",
    MakerspaceMembership.Role.INVENTORY_MANAGER.value: "staff",
    MakerspaceMembership.Role.PRINT_MANAGER.value: "staff",
    "requester": "requester",
}

_STREAM_ROLES = {
    "hardware": (
        MakerspaceMembership.Role.SPACE_MANAGER.value,
        MakerspaceMembership.Role.INVENTORY_MANAGER.value,
    ),
    "printing": (
        MakerspaceMembership.Role.SPACE_MANAGER.value,
        MakerspaceMembership.Role.PRINT_MANAGER.value,
    ),
}


def valid_targets_for_stream(stream):
    roles = _STREAM_ROLES.get(stream)
    if roles is None:
        return ()
    return ("requester", *roles)


def _target_value(target):
    return getattr(target, "value", target)


def is_event_mutable(stream, audience, event) -> bool:
    return event in EVENT_CATALOG.get((stream, audience), ())


def role_muted(makerspace, stream, event, role) -> bool:
    try:
        if not is_event_mutable(stream, "staff", event):
            return False
        return EmailNotificationMute.objects.filter(
            makerspace=makerspace,
            target=_target_value(role),
            stream=stream,
            event=event,
            audience="staff",
        ).exists()
    except Exception:
        logger.warning(
            "email_notification_role_mute_check_failed",
            extra={
                "makerspace_id": getattr(makerspace, "pk", None),
                "stream": stream,
                "event": event,
                "role": role,
            },
            exc_info=True,
        )
        return is_event_mutable(stream, "staff", event)


def is_requester_muted(makerspace, stream, event) -> bool:
    try:
        if not is_event_mutable(stream, "requester", event):
            return False
        return EmailNotificationMute.objects.filter(
            makerspace=makerspace,
            target="requester",
            stream=stream,
            event=event,
            audience="requester",
        ).exists()
    except Exception:
        logger.warning(
            "email_notification_requester_mute_check_failed",
            extra={
                "makerspace_id": getattr(makerspace, "pk", None),
                "stream": stream,
                "event": event,
            },
            exc_info=True,
        )
        return is_event_mutable(stream, "requester", event)


def muted_targets(makerspace, stream, event) -> set[str]:
    try:
        audiences = [
            audience
            for audience in ("requester", "staff")
            if is_event_mutable(stream, audience, event)
        ]
        if not audiences:
            return set()
        valid_targets = valid_targets_for_stream(stream)
        return set(
            EmailNotificationMute.objects.filter(
                makerspace=makerspace,
                stream=stream,
                event=event,
                audience__in=audiences,
                target__in=valid_targets,
            ).values_list("target", flat=True)
        )
    except Exception:
        logger.warning(
            "email_notification_muted_targets_check_failed",
            extra={
                "makerspace_id": getattr(makerspace, "pk", None),
                "stream": stream,
                "event": event,
            },
            exc_info=True,
        )
        return _fail_closed_targets(stream, event)


def _fail_closed_targets(stream, event) -> set[str]:
    targets = set()
    if is_event_mutable(stream, "requester", event):
        targets.add("requester")
    if is_event_mutable(stream, "staff", event):
        targets.update(valid_targets_for_stream(stream)[1:])
    return targets


