import hashlib
import hmac
import logging
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class FrontendHMACMiddleware:
    """Validate signed client requests for protected API paths using the ApiClient registry."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_validate(request) and not self._is_valid(request):
            return JsonResponse({"detail": "Invalid client signature."}, status=401)
        return self.get_response(request)

    def _should_validate(self, request):
        if request.method == "OPTIONS" or not settings.API_CLIENT_AUTH_REQUIRED:
            return False
        return any(
            request.path.startswith(p) for p in settings.HMAC_PROTECTED_PATH_PREFIXES
        )

    def _is_valid(self, request):
        try:
            from apps.apiclients.models import ApiClient

            client_id = request.headers.get("X-Client-Id", "")
            timestamp = request.headers.get("X-Timestamp", "")
            signature = request.headers.get("X-Signature", "")
            if not (client_id and timestamp and signature):
                return False

            client = ApiClient.objects.filter(
                client_id=client_id, is_active=True
            ).first()
            if client is None:
                return False

            if not self._origin_ok(request, client):
                return False

            try:
                skew = abs(int(time.time()) - int(timestamp))
            except ValueError:
                return False
            if skew > settings.HMAC_MAX_CLOCK_SKEW_SECONDS:
                return False

            message = b"\n".join([
                request.method.upper().encode(),
                request.get_full_path().encode(),
                timestamp.encode(),
                request.body,
            ])
            expected = hmac.new(
                client.get_secret().encode(), message, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        except Exception:  # fail safe - never 500 the request flow
            logger.exception("ApiClient signature validation failed")
            return False

    def _origin_ok(self, request, client):
        # Fail closed (review fix #4): a client with no configured origins is rejected,
        # so the exact-origin check can never be skipped by omission. The model + admin
        # also require at least one origin (ApiClient.clean).
        if not client.allowed_origins:
            return False
        raw = request.headers.get("Origin") or request.headers.get("Referer", "")
        if not raw:
            return False
        parts = urlsplit(raw)
        candidate = f"{parts.scheme}://{parts.netloc}" if parts.scheme else ""
        return candidate in set(client.allowed_origins)
