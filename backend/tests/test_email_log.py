import pytest
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.integrations.dispatch import dispatch_email
from apps.integrations.email import send_makerspace_email, send_password_reset_email
from apps.integrations.models import EmailLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership

pytestmark = pytest.mark.django_db


def make_space(slug, **kwargs):
    return Makerspace.objects.create(name=slug, slug=slug, **kwargs)


def make_user(username, **kwargs):
    return get_user_model().objects.create_user(
        username=username,
        email=kwargs.pop("email", f"{username}@example.com"),
        access_status=kwargs.pop("access_status", User.AccessStatus.ACTIVE),
        **kwargs,
    )


def make_member(username, makerspace, role=MakerspaceMembership.Role.SPACE_MANAGER):
    user = make_user(username, role=User.Role.SPACE_MANAGER)
    MakerspaceMembership.objects.create(user=user, makerspace=makerspace, role=role)
    return user


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def log_url(makerspace):
    return f"/api/v1/admin/makerspace/{makerspace.id}/email-logs"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_dispatch_email_creates_sent_log_row():
    makerspace = make_space("email-log-dispatch")

    log = dispatch_email(
        to_email="borrower@example.com",
        subject="Ready",
        text_body="Your item is ready.",
        makerspace=makerspace,
        stream="hardware",
        event="request_accepted",
        audience="requester",
        sync=True,
    )

    assert EmailLog.objects.count() == 1
    log.refresh_from_db()
    assert log.status == EmailLog.Status.SENT
    assert log.sent_at is not None
    assert log.attempts == 1
    assert log.stream == "hardware"


def test_dispatch_email_failure_logs_error_without_raising(monkeypatch):
    makerspace = make_space("email-log-failure")

    def fail_send(self):
        raise RuntimeError("smtp unavailable")

    monkeypatch.setattr(EmailMultiAlternatives, "send", fail_send)

    log = dispatch_email(
        to_email="borrower@example.com",
        subject="Ready",
        text_body="Your item is ready.",
        makerspace=makerspace,
        sync=True,
    )

    log.refresh_from_db()
    assert log.status == EmailLog.Status.FAILED
    assert log.sent_at is None
    assert log.attempts == 1
    assert "smtp unavailable" in log.error


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_password_reset_email_logs_platform_account_stream(mailoutbox):
    reset_url = "https://example.test/reset?uid=abc&token=secret-live-token"
    sent = send_password_reset_email("person@example.com", reset_url)

    assert sent == 1
    log = EmailLog.objects.get()
    assert log.makerspace is None
    assert log.connection_kind == "platform"
    assert log.stream == "account"
    assert log.event == "password_reset"
    assert log.audience == "user"
    assert log.status == EmailLog.Status.SENT
    # P1: the live reset token must NOT be persisted in the log (DB/admin),
    # but it must still be delivered in the actual email body.
    assert log.text_body == ""
    assert log.html_body == ""
    assert "secret-live-token" not in log.text_body
    assert reset_url in mailoutbox[0].body


def test_send_makerspace_email_returns_true_sent_count(monkeypatch):
    makerspace = make_space("email-log-sent-count")

    def selective_send(self):
        if self.to == ["fail@example.com"]:
            raise RuntimeError("smtp rejected")
        return 1

    monkeypatch.setattr(EmailMultiAlternatives, "send", selective_send)

    sent = send_makerspace_email(
        makerspace,
        "Subject",
        "Body",
        ["ok@example.com", "fail@example.com", ""],
        stream="hardware",
        event="request_issued",
        audience="requester",
        sync=True,
    )

    assert sent == 1
    assert EmailLog.objects.filter(status=EmailLog.Status.SENT).count() == 1
    assert EmailLog.objects.filter(status=EmailLog.Status.FAILED).count() == 1


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_manager_lists_own_email_logs_and_response_excludes_bodies():
    makerspace = make_space("email-log-api-own")
    manager = make_member("email-log-api-manager", makerspace)
    dispatch_email(
        to_email="person@example.com",
        subject="Logged",
        text_body="Sensitive text",
        html_body="<p>Sensitive html</p>",
        makerspace=makerspace,
        stream="hardware",
        event="request_received",
        audience="requester",
        sync=True,
    )

    response = authenticated_client(manager).get(log_url(makerspace))

    assert response.status_code == 200
    row = response.data["results"][0]
    assert row["to_email"] == "person@example.com"
    assert row["stream"] == "hardware"
    assert row["status"] == "sent"
    assert "text_body" not in row
    assert "html_body" not in row


def test_email_log_api_rejects_invalid_status_filter():
    makerspace = make_space("email-log-api-invalid-status")
    manager = make_member("email-log-api-invalid-manager", makerspace)

    response = authenticated_client(manager).get(f"{log_url(makerspace)}?status=lost")

    assert response.status_code == 400


def test_email_log_api_returns_404_for_cross_tenant_hidden_and_archived():
    own_space = make_space("email-log-api-own-404")
    other_space = make_space("email-log-api-other-404")
    hidden_space = make_space(
        "email-log-api-hidden-404",
        superadmin_access_enabled=False,
    )
    archived_space = make_space("email-log-api-archived-404", archived_at=timezone.now())
    manager = make_member("email-log-api-own-manager-404", own_space)
    superadmin = make_user(
        "email-log-api-superadmin-404",
        role=User.Role.SUPERADMIN,
        is_staff=True,
        is_superuser=True,
    )
    make_member(
        "email-log-api-archived-manager-404",
        archived_space,
        MakerspaceMembership.Role.SPACE_MANAGER,
    )

    manager_client = authenticated_client(manager)
    assert manager_client.get(log_url(other_space)).status_code == 404
    assert manager_client.get(log_url(archived_space)).status_code == 404
    assert authenticated_client(superadmin).get(log_url(hidden_space)).status_code == 404


def test_can_retry_covers_failed_and_stalled_pending():
    from datetime import timedelta

    from apps.admin_api.views_email_logs import STALE_PENDING_AFTER, _can_retry

    makerspace = make_space("email-log-canretry")
    base = dict(makerspace=makerspace, to_email="x@y.com", subject="s", text_body="body")
    failed = EmailLog.objects.create(**base, status=EmailLog.Status.FAILED)
    sent = EmailLog.objects.create(**base, status=EmailLog.Status.SENT)
    fresh_pending = EmailLog.objects.create(**base, status=EmailLog.Status.PENDING)
    no_body = EmailLog.objects.create(
        makerspace=makerspace, to_email="x@y.com", subject="s", status=EmailLog.Status.FAILED
    )

    assert _can_retry(failed) is True
    assert _can_retry(sent) is False
    assert _can_retry(fresh_pending) is False  # not yet stalled
    assert _can_retry(no_body) is False  # nothing to resend

    # Age the pending row past the stall window -> retryable.
    EmailLog.objects.filter(pk=fresh_pending.pk).update(
        updated_at=timezone.now() - STALE_PENDING_AFTER - timedelta(minutes=1)
    )
    fresh_pending.refresh_from_db()
    assert _can_retry(fresh_pending) is True


def test_retry_endpoint_allows_stalled_pending_but_not_fresh():
    from datetime import timedelta

    from apps.admin_api.views_email_logs import STALE_PENDING_AFTER

    makerspace = make_space("email-log-retry-stale")
    manager = make_member("email-log-retry-mgr", makerspace)
    client = authenticated_client(manager)
    log = EmailLog.objects.create(
        makerspace=makerspace,
        to_email="x@y.com",
        subject="s",
        text_body="body",
        status=EmailLog.Status.PENDING,
    )
    retry_url = f"{log_url(makerspace)}/{log.id}/retry"

    # Fresh pending is not retryable (it may still be in flight).
    assert client.post(retry_url).status_code == 400

    EmailLog.objects.filter(pk=log.pk).update(
        updated_at=timezone.now() - STALE_PENDING_AFTER - timedelta(minutes=1)
    )
    # Stalled pending (crashed at-most-once delivery) is recoverable.
    assert client.post(retry_url).status_code == 200
