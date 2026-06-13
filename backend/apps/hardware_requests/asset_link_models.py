from django.db import models
from django.utils import timezone


class HardwareRequestItemAsset(models.Model):
    class Outcome(models.TextChoices):
        ISSUED = "issued", "Issued"
        RETURNED = "returned", "Returned"
        DAMAGED = "damaged", "Damaged"
        LOST = "lost", "Lost"

    request_item = models.ForeignKey(
        "hardware_requests.HardwareRequestItem",
        on_delete=models.CASCADE,
        related_name="asset_links",
    )
    asset = models.ForeignKey(
        "inventory.InventoryAsset",
        on_delete=models.PROTECT,
        related_name="+",
    )
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.ISSUED,
        db_index=True,
    )
    issued_at = models.DateTimeField(default=timezone.now)
    returned_at = models.DateTimeField(null=True, blank=True)
    return_event = models.ForeignKey(
        "hardware_requests.ReturnEvent",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["request_item", "asset"],
                name="uniq_request_item_asset",
            ),
        ]
        indexes = [
            models.Index(fields=["request_item", "outcome"]),
        ]
