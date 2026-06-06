import uuid

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
