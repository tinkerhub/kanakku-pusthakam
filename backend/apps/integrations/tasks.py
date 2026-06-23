import random

from celery import shared_task
from django.db import transaction

from apps.integrations.dispatch import _deliver
from apps.integrations.models import EmailLog


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def deliver_email_task(self, log_id):
    with transaction.atomic():
        # select_related avoids a second query when _deliver reads log.makerspace to
        # resolve the per-makerspace SMTP connection. makerspace is nullable, so the join
        # is a LEFT OUTER JOIN — lock only the EmailLog row (of="self"), since Postgres
        # rejects FOR UPDATE on the nullable side of an outer join.
        log = (
            EmailLog.objects.select_related("makerspace")
            .select_for_update(of=("self",))
            .filter(pk=log_id)
            .first()
        )
        if log is None or log.status == EmailLog.Status.SENT:
            return
        _deliver(log)
    log.refresh_from_db()
    if log.status == EmailLog.Status.FAILED:
        # Exponential backoff + jitter so an SMTP outage doesn't trigger synchronised
        # retry bursts across the queue (~1m, 2m, 4m, capped at 10m, with ±20% jitter).
        base = min(60 * (2 ** self.request.retries), 600)
        countdown = int(base * (0.8 + 0.4 * random.random()))
        try:
            raise self.retry(countdown=countdown)
        except self.MaxRetriesExceededError:
            return
