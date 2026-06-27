import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.warranty.models import WarrantyDocument

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=WarrantyDocument)
def delete_warranty_document_object(sender, instance, **kwargs):
    """Best-effort remove the private bill from object storage on ANY delete path.

    `WarrantyDocumentDeleteView` already deletes the object, but a WarrantyDocument
    can also be removed by a CASCADE when its asset/printer/warranty/makerspace is
    deleted (printer-delete API, Django admin, makerspace purge). Without this the
    private file would orphan in object storage with no DB row left to collect.

    The actual storage delete is deferred to `transaction.on_commit`: `post_delete`
    fires BEFORE the DB commit, so a delete inside a transaction that later rolls back
    (e.g. the makerspace-purge object-graph atomic block) must NOT remove the S3 object
    while the row is restored. on_commit runs immediately when there is no open
    transaction, so the non-atomic delete paths are unaffected.
    """
    object_key = instance.object_key
    if not object_key:
        return

    def _delete():
        # Local import keeps the storage (boto3/settings) dependency out of app loading.
        from apps.warranty import storage

        try:
            storage.delete_object(object_key)
        except Exception:  # pragma: no cover - delete_object is already best-effort
            logger.exception("Failed to delete warranty document object %s.", object_key)

    transaction.on_commit(_delete)
