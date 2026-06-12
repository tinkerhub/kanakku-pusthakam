from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.crypto import get_random_string


def generate_publishable_key():
    return f"pk_{get_random_string(32)}"


def generate_public_code():
    return get_random_string(4, allowed_chars="ABCDEFGHJKLMNPQRSTUVWXYZ23456789")


class Makerspace(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, db_index=True)
    public_code = models.CharField(
        max_length=4,
        unique=True,
        db_index=True,
        default=generate_public_code,
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9]{4}$",
                message="Public code must be exactly 4 uppercase letters or digits.",
            )
        ],
    )
    location = models.CharField(max_length=200, blank=True)
    public_inventory_enabled = models.BooleanField(default=True)
    public_api_key = models.CharField(
        max_length=40,
        editable=False,
        default=generate_publishable_key,
    )
    cors_allowed_origins = models.JSONField(default=list, blank=True)
    telegram_group_chat_id = models.CharField(max_length=64, blank=True)
    telegram_bot_token = models.CharField(max_length=200, blank=True)
    smtp_host = models.CharField(max_length=200, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=200, blank=True)
    smtp_password = models.CharField(max_length=200, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_from_email = models.EmailField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_makerspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["public_api_key"],
                name="uniq_makerspace_public_api_key",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.public_code = (self.public_code or "").upper()
        super().save(*args, **kwargs)


class MakerspaceMembership(models.Model):
    # Role is per-makerspace: this membership is what grants a user space-manager/guest-admin
    # rights for THIS makerspace. Global User.role stays for superadmin. Enforcement
    # of scoping/suspension is centralized in the Phase 2 RBAC layer, not here.
    class Role(models.TextChoices):
        SPACE_MANAGER = "space_manager", "Space Manager"
        GUEST_ADMIN = "guest_admin", "Guest Admin"
        INVENTORY_MANAGER = "inventory_manager", "Inventory Manager"
        PRINT_MANAGER = "print_manager", "Print Manager"

    makerspace = models.ForeignKey(
        Makerspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="makerspace_memberships",
        limit_choices_to={"is_active": True},
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.SPACE_MANAGER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["makerspace", "user"],
                name="uniq_makerspace_user",
            ),
        ]

    def clean(self):
        # Block assigning a membership to a deactivated account (covers the User-side
        # inline where user is the parent and limit_choices_to does not apply).
        if self.user_id and not self.user.is_active:
            raise ValidationError("Cannot assign a makerspace to an inactive user.")

    def __str__(self):
        return f"{self.user} @ {self.makerspace.slug} ({self.role})"
