from django import forms
from django.contrib import admin

from config.admin_access import SuperuserOnlyModelAdmin

from apps.integrations import admin_email_logs  # noqa: F401
from apps.integrations import admin_notification_mutes  # noqa: F401
from apps.integrations.email_registry import template_keys
from apps.integrations.models import EmailLayout, EmailTemplate, PlatformEmailSettings
from apps.integrations.smtp_validation import validate_smtp_settings


class PlatformEmailSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = PlatformEmailSettings
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        validate_smtp_settings(cleaned, self.instance)
        return cleaned

@admin.register(PlatformEmailSettings)
class PlatformEmailSettingsAdmin(SuperuserOnlyModelAdmin, admin.ModelAdmin):
    form = PlatformEmailSettingsAdminForm
    list_display = ("smtp_host", "smtp_port", "from_email", "updated_at")
    # smtp_password holds the Fernet-encrypted value; never edit it as raw ciphertext
    # in the admin. The React superadmin Platform Email panel is the write surface.
    exclude = ("smtp_password",)
    readonly_fields = ("updated_at",)


class EmailTemplateAdminForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = "__all__"

    def clean_key(self):
        key = self.cleaned_data["key"]
        if key not in template_keys():
            raise forms.ValidationError("Unknown email template key.")
        return key


@admin.register(EmailTemplate)
class EmailTemplateAdmin(SuperuserOnlyModelAdmin, admin.ModelAdmin):
    # Model save() sanitizes html_body via nh3, so admin edits are sanitized too.
    form = EmailTemplateAdminForm
    list_display = ("makerspace", "key", "subject", "is_active", "updated_at")
    list_filter = ("makerspace", "is_active")
    search_fields = ("key", "subject")
    readonly_fields = ("created_at", "updated_at")


class EmailLayoutAdminForm(forms.ModelForm):
    class Meta:
        model = EmailLayout
        fields = "__all__"

    def clean_html(self):
        # Mirror the API serializer so a bad layout shows an inline admin error instead of
        # the model save() ValidationError surfacing as a 500. Check the sanitized value,
        # since nh3 may strip markup the token lived in.
        from apps.integrations.email_render import sanitize_email_html

        value = self.cleaned_data.get("html", "") or ""
        if value.strip() and "{{ content }}" not in sanitize_email_html(value):
            raise forms.ValidationError("The layout must contain the {{ content }} token.")
        return value


@admin.register(EmailLayout)
class EmailLayoutAdmin(SuperuserOnlyModelAdmin, admin.ModelAdmin):
    # Model save() sanitizes html via nh3 and enforces the content slot as a backstop.
    form = EmailLayoutAdminForm
    list_display = ("makerspace", "is_active", "updated_at")
    list_filter = ("makerspace", "is_active")
    readonly_fields = ("created_at", "updated_at")
