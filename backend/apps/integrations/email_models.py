from django.db import models


class EmailTemplate(models.Model):
    makerspace = models.ForeignKey(
        "makerspaces.Makerspace",
        on_delete=models.CASCADE,
        related_name="email_templates",
    )
    key = models.CharField(max_length=64)
    subject = models.CharField(max_length=255)
    text_body = models.TextField()
    html_body = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("makerspace", "key"),)

    def __str__(self):
        return f"{self.makerspace}:{self.key}"

    def save(self, *args, **kwargs):
        from apps.integrations.email_render import sanitize_email_html

        if self.html_body:
            self.html_body = sanitize_email_html(self.html_body)
        super().save(*args, **kwargs)


class EmailLayout(models.Model):
    makerspace = models.OneToOneField(
        "makerspaces.Makerspace",
        on_delete=models.CASCADE,
        related_name="email_layout",
    )
    html = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.makerspace} layout"

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError

        from apps.integrations.email_render import sanitize_email_html

        if self.html:
            self.html = sanitize_email_html(self.html)
        # Backstop (covers the Django /control/ admin + shell paths the API serializer
        # doesn't): a non-blank layout must keep the {{ content }} slot AFTER sanitize, or
        # the renderer's .replace() drops the body from every HTML email for this space.
        if self.html.strip() and "{{ content }}" not in self.html:
            raise ValidationError("The layout must contain the {{ content }} token.")
        super().save(*args, **kwargs)
