import re

import nh3
from django.db import migrations
from django.db.models import Q

from apps.integrations.email_render import (
    ALLOWED_ATTRIBUTES,
    ALLOWED_TAGS,
    URL_SCHEMES,
)

# The old HardwareEmailTemplate rows were authored for Django's Template engine. The new
# renderer only substitutes flat {{ snake_case }} tokens, so a CUSTOMIZED legacy row would
# otherwise emit literal `{{ request.id }}` / `{% if %}`. Best-effort translate the known
# variable set to the flat equivalents, strip block tags, and drop any remaining dotted
# (object-access) tokens so no raw template syntax leaks into a sent email.
_LEGACY_VAR_MAP = {
    "makerspace.name": "makerspace_name",
    "request.id": "request_id",
    "request.status": "status",
}
_DOTTED_TOKEN_RE = re.compile(r"\{\{\s*[a-zA-Z0-9_]+\.[a-zA-Z0-9_.]+\s*\}\}")
_BLOCK_TAG_RE = re.compile(r"\{%.*?%\}", re.DOTALL)
# The two known optional blocks in the legacy defaults map cleanly onto the precomputed
# flat block vars the send site fills (e.g. "\n\nReturn by: <date>" or ""); translate the
# WHOLE block so we don't leave a dangling "Return by:"/"Reason:" label with no value.
_OPTIONAL_BLOCK_RES = (
    (
        re.compile(r"\{%\s*if\s+request\.return_due_at\s*%\}.*?\{%\s*endif\s*%\}", re.DOTALL),
        "{{ return_due_block }}",
    ),
    (
        re.compile(r"\{%\s*if\s+request\.rejection_reason\s*%\}.*?\{%\s*endif\s*%\}", re.DOTALL),
        "{{ reason_block }}",
    ),
)


def _translate_legacy(text):
    if not text:
        return text
    for dotted, flat in _LEGACY_VAR_MAP.items():
        text = re.sub(
            r"\{\{\s*" + re.escape(dotted) + r"\s*\}\}",
            "{{ " + flat + " }}",
            text,
        )
    # Map the known optional blocks to flat block vars BEFORE the generic strip.
    for pattern, replacement in _OPTIONAL_BLOCK_RES:
        text = pattern.sub(replacement, text)
    # Remove any remaining {% ... %} block tags, keeping their inner text.
    text = _BLOCK_TAG_RE.sub("", text)
    # Any dotted token left is unmappable object access the flat renderer can't fill —
    # drop it rather than leak `{{ request.foo }}` into the email.
    text = _DOTTED_TOKEN_RE.sub("", text)
    return text


def migrate_hardware_templates(apps, schema_editor):
    HardwareEmailTemplate = apps.get_model(
        "hardware_requests",
        "HardwareEmailTemplate",
    )
    EmailTemplate = apps.get_model("integrations", "EmailTemplate")

    for old in HardwareEmailTemplate.objects.all():
        translated_html = _translate_legacy(old.html_body)
        html_body = (
            nh3.clean(
                translated_html,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                url_schemes=URL_SCHEMES,
            )
            if translated_html
            else ""
        )
        EmailTemplate.objects.update_or_create(
            makerspace_id=old.makerspace_id,
            key="hw_" + old.key,
            defaults={
                "subject": _translate_legacy(old.subject),
                "text_body": _translate_legacy(old.text_body),
                "html_body": html_body,
                "is_active": old.is_active,
            },
        )


def restore_hardware_templates(apps, schema_editor):
    HardwareEmailTemplate = apps.get_model(
        "hardware_requests",
        "HardwareEmailTemplate",
    )
    EmailTemplate = apps.get_model("integrations", "EmailTemplate")

    templates = EmailTemplate.objects.filter(
        Q(key__startswith="hw_request_") | Q(key="hw_return_reminder")
    )
    for template in templates:
        HardwareEmailTemplate.objects.update_or_create(
            makerspace_id=template.makerspace_id,
            key=template.key.removeprefix("hw_"),
            defaults={
                "subject": template.subject,
                "text_body": template.text_body,
                "html_body": template.html_body,
                "is_active": template.is_active,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0002_emaillayout_emailtemplate"),
        ("hardware_requests", "0016_publictoolloan_return_evidence_notes"),
    ]

    operations = [
        migrations.RunPython(
            migrate_hardware_templates,
            restore_hardware_templates,
        ),
    ]
