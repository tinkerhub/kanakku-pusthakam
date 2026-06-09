import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.makerspaces.models import Makerspace


def generate_box_code():
    return uuid.uuid4().hex


class Box(models.Model):
    # `code` is a GLOBALLY-unique opaque QR payload (intentional; stricter than per-makerspace).
    makerspace = models.ForeignKey(
        Makerspace,
        on_delete=models.CASCADE,
        related_name="boxes",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    code = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        default=generate_box_code,
    )
    label = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["makerspace", "label"],
                name="uniq_box_label_per_makerspace",
            ),
        ]

    def __str__(self):
        return f"{self.label} [{self.makerspace.slug}]"

    def clean(self):
        if self.parent_id:
            if self.parent.makerspace_id != self.makerspace_id:
                raise ValidationError(
                    {"parent": "Parent box must be in the same makerspace."}
                )
            seen = set()
            node = self.parent
            while node is not None:
                if node.pk == self.pk or node.pk in seen:
                    raise ValidationError(
                        {"parent": "A box cannot be its own ancestor."}
                    )
                seen.add(node.pk)
                node = node.parent
