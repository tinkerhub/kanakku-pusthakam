from importlib.util import find_spec

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class CheckinConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.checkin"

    def ready(self):
        # Normalize like the client does (client.py lowercases the mode), so
        # CHECKIN_MODE=HTTP cannot slip past startup validation.
        mode = (getattr(settings, "CHECKIN_MODE", "stub") or "stub").lower()
        if mode != "http":
            return

        if not settings.CHECKIN_API_URL:
            raise ImproperlyConfigured(
                "CHECKIN_API_URL must be set when CHECKIN_MODE=http."
            )
        timeout = getattr(settings, "CHECKIN_TIMEOUT", None)
        if timeout is None or timeout <= 0:
            raise ImproperlyConfigured(
                "CHECKIN_TIMEOUT must be a positive number when CHECKIN_MODE=http."
            )
        if find_spec("requests") is None:
            raise ImproperlyConfigured(
                "The requests package must be installed when CHECKIN_MODE=http."
            )
