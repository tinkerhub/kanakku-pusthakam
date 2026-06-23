"""Phase 3 (email infra / async) regression tests: at-most-once delivery semantics,
commit-time enqueue, and broker-down fail-safe — the async paths the autouse eager
setting otherwise hides."""

import pytest

from apps.integrations import dispatch, tasks
from apps.integrations.models import EmailLog
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_celery_acks_late_disabled_for_at_most_once(settings):
    # acks_late=True would re-run a crashed task and double-send (SMTP isn't
    # transactional). At-most-once + the visible Retry action is the chosen trade-off.
    assert settings.CELERY_TASK_ACKS_LATE is False


def test_dispatch_enqueues_on_commit_without_delivering_inline(
    django_capture_on_commit_callbacks, monkeypatch, settings
):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    calls = []
    monkeypatch.setattr(tasks.deliver_email_task, "delay", lambda log_id: calls.append(log_id))
    makerspace = make_space("enqueue-oncommit")
    with django_capture_on_commit_callbacks(execute=True):
        log = dispatch.dispatch_email(
            to_email="a@b.com",
            subject="s",
            text_body="body",
            makerspace=makerspace,
            sync=False,
        )
        # Async path: the row is queued, not delivered inline.
        assert log.status == EmailLog.Status.PENDING
    assert calls == [log.id]


def test_enqueue_marks_failed_when_broker_down(monkeypatch):
    makerspace = make_space("enqueue-broker-down")
    log = EmailLog.objects.create(makerspace=makerspace, to_email="a@b.com", subject="s")

    def boom(log_id):
        raise RuntimeError("broker unreachable")

    monkeypatch.setattr(tasks.deliver_email_task, "delay", boom)
    # Fail-safe: a down broker marks the row FAILED, never raises into the request.
    dispatch._enqueue(log.id)
    log.refresh_from_db()
    assert log.status == EmailLog.Status.FAILED
    assert "enqueue failed" in log.error.lower()
