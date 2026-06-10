from django.core.exceptions import ValidationError
from django.db import models

from apps.makerspaces.models import Makerspace


class PublicAvailabilityMode(models.TextChoices):
    EXACT_COUNT = "exact_count", "Exact Count"
    STATUS_ONLY = "status_only", "Status Only"
    HIDDEN = "hidden", "Hidden"


class TrackingMode(models.TextChoices):
    QUANTITY = "quantity", "Quantity"
    INDIVIDUAL = "individual", "Individual"


class InventoryProduct(models.Model):
    makerspace = models.ForeignKey(
        Makerspace,
        on_delete=models.CASCADE,
        related_name="products",
    )
    box = models.ForeignKey(
        "boxes.Box",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # Individual-mode availability still derives from the quantity buckets until the
    # Unit service layer (Phase 6); tracking_mode is just a classification flag for now.
    tracking_mode = models.CharField(
        max_length=20,
        choices=TrackingMode.choices,
        default=TrackingMode.QUANTITY,
    )
    total_quantity = models.PositiveIntegerField(default=0)
    available_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    issued_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0)
    lost_quantity = models.PositiveIntegerField(default=0)
    is_public = models.BooleanField(default=True)
    show_public_count = models.BooleanField(default=False)
    public_availability_mode = models.CharField(
        max_length=20,
        choices=PublicAvailabilityMode.choices,
        default=PublicAvailabilityMode.STATUS_ONLY,
    )
    storage_location = models.CharField(max_length=200, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["makerspace", "is_public", "is_archived"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_quantity__gte=0),
                name="qty_total_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(available_quantity__gte=0),
                name="qty_available_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__gte=0),
                name="qty_reserved_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(issued_quantity__gte=0),
                name="qty_issued_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(damaged_quantity__gte=0),
                name="qty_damaged_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(lost_quantity__gte=0),
                name="qty_lost_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total_quantity__gte=(
                        models.F("available_quantity")
                        + models.F("reserved_quantity")
                        + models.F("issued_quantity")
                        + models.F("damaged_quantity")
                        + models.F("lost_quantity")
                    )
                ),
                name="qty_sum_within_total",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.makerspace.slug})"

    def clean(self):
        if self.box_id and self.box.makerspace_id != self.makerspace_id:
            raise ValidationError(
                {"box": "Box must belong to the same makerspace as the product."}
            )
