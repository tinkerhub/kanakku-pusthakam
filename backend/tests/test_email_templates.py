from decimal import Decimal

import pytest
from django.core import mail
from django.test import override_settings

from apps.hardware_requests import notifications, staff_notifications
from apps.integrations.email_models import EmailLayout, EmailTemplate
from apps.integrations.email_registry import get_template, template_keys
from apps.integrations.email_render import render_email_template, sanitize_email_html
from apps.makerspaces.models import MakerspaceMembership
from apps.printing import emails as print_emails
from apps.printing import views_requests as print_views_requests
from apps.printing import workflow as print_workflow
from tests.test_printing import (
    authenticated_client as print_authenticated_client,
    make_bucket,
    make_print_manager,
    make_request as make_print_request,
    make_user as make_print_user,
    request_list_url as print_request_list_url,
)
from tests.test_request_workflow import (
    make_hardware_request,
    make_member,
    make_product,
    make_space,
)

pytestmark = pytest.mark.django_db

XSS = '<img src=x onerror=alert(1)>'


def reset_outbox():
    mail.outbox = []


def message_html(message):
    assert len(message.alternatives) == 1
    html, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    return html


def render_received(makerspace, request_id=1, status="pending"):
    return render_email_template(
        makerspace,
        "hw_request_received",
        {"makerspace_name": makerspace.name, "request_id": request_id, "status": status},
    )


def test_registry_exposes_all_phase_one_template_keys():
    keys = template_keys()

    assert len(keys) == 27
    assert len(keys) == len(set(keys))
    assert get_template("hw_request_received")["family"] == "hardware"
    assert get_template("print_submitted")["family"] == "printing"


def test_renderer_uses_flat_placeholders_without_leaking_objects_or_unknowns():
    makerspace = make_space("template-flat")
    EmailTemplate.objects.create(
        makerspace=makerspace, key="hw_request_received",
        subject="Secret {{ makerspace_smtp_password }} {{ request.id }}",
        text_body="Unknown={{ unknown_var }} dotted={{ request.id }}",
        html_body="<p>Unknown={{ unknown_var }} dotted={{ request.id }}</p>",
    )

    rendered = render_received(makerspace, request_id=7)

    combined = "\n".join(rendered.values())
    assert "makerspace_smtp_password" not in combined
    assert "Unknown=" in rendered["text_body"]
    assert "Unknown={{" not in rendered["text_body"]
    assert "{{ request.id }}" in combined
    assert "object at 0x" not in combined


def test_renderer_escapes_scalar_variables_in_html_but_not_text():
    makerspace = make_space("template-escape")
    payload = '<b>x</b> "quoted"'
    EmailTemplate.objects.create(
        makerspace=makerspace, key="hw_request_received", subject="Escaped",
        text_body="Status: {{ status }}",
        html_body="<p>Status: {{ status }}</p>",
    )

    rendered = render_email_template(makerspace, "hw_request_received", {"status": payload})

    assert payload in rendered["text_body"]
    # The real security property: angle brackets stay escaped so the value can never
    # become live markup. (nh3's final pass re-serializes a &quot; in *text* content
    # back to a literal " — harmless, since quotes are only dangerous inside attrs.)
    assert "&lt;b&gt;x&lt;/b&gt;" in rendered["html_body"]
    assert "<b>x</b>" not in rendered["html_body"]
    assert payload not in rendered["html_body"]


def test_trusted_html_send_site_builders_escape_malicious_input():
    makerspace = make_space("template-builder-escape")
    product = make_product(makerspace, name=XSS)
    hardware_request = make_hardware_request(makerspace, product)

    item_html = notifications._item_list_html(hardware_request)
    assert "&lt;img" in item_html
    assert "<img" not in item_html

    hardware_request.requester_contact_email = XSS
    hardware_request.rejection_reason = XSS
    hardware_request.save(
        update_fields=["requester_contact_email", "rejection_reason", "updated_at"]
    )
    staff_html = staff_notifications._staff_summary_html(hardware_request)
    assert "&lt;img" in staff_html
    assert "<img" not in staff_html

    bucket = make_bucket(makerspace)
    requester = make_print_user("template-builder-print-user", access_status="active")
    print_request = make_print_request(bucket, requester, title=XSS)
    print_request.reason = XSS
    print_request.save(update_fields=["reason", "updated_at"])
    print_html = print_emails._staff_print_body_html("rejected", print_request)
    assert "&lt;img" in print_html
    assert "<img" not in print_html


def test_template_and_final_sanitize_strip_unsafe_html():
    makerspace = make_space("template-sanitize")
    unsafe = (
        '<script>alert(1)</script>'
        '<a href="javascript:alert(1)">bad</a>'
        '<img src=x onerror=alert(1)>'
        '<div onerror="alert(1)">safe text</div>'
    )
    EmailTemplate.objects.create(
        makerspace=makerspace, key="hw_request_received",
        subject="Unsafe", text_body="Body", html_body=unsafe,
    )

    rendered = render_email_template(makerspace, "hw_request_received", {})
    direct = sanitize_email_html(unsafe)

    for html in (rendered["html_body"], direct):
        lowered = html.lower()
        assert "<script" not in lowered
        assert "javascript:" not in lowered
        assert "<img" not in lowered
        assert "onerror" not in lowered


def test_layout_slot_wraps_content_and_default_layout_is_used_without_override():
    makerspace = make_space("template-layout")

    default_rendered = render_received(makerspace, request_id=5)
    assert "Makerspace notifications" in default_rendered["html_body"]
    assert "request #5 was received" in default_rendered["html_body"]

    EmailLayout.objects.create(
        makerspace=makerspace, html="<div><p>BRAND</p>{{ content }}</div>"
    )
    custom_rendered = render_received(makerspace, request_id=6)

    assert "BRAND" in custom_rendered["html_body"]
    assert "request #6 was received" in custom_rendered["html_body"]


def test_renderer_uses_defaults_and_active_makerspace_overrides_only():
    makerspace = make_space("template-defaults")
    inactive_space = make_space("template-inactive")

    rendered = render_received(makerspace, request_id=9)
    assert rendered["subject"] == f"{makerspace.name} request received"
    assert "Status: pending" in rendered["text_body"]

    EmailTemplate.objects.create(
        makerspace=makerspace, key="hw_request_received",
        subject="Custom subject {{ request_id }}",
        text_body="Custom text",
        html_body="<p>Custom html</p>",
    )
    custom = render_email_template(makerspace, "hw_request_received", {"request_id": 10})
    assert custom["subject"] == "Custom subject 10"
    assert "Custom text" in custom["text_body"]

    EmailTemplate.objects.create(
        makerspace=inactive_space, key="hw_request_received",
        subject="Inactive subject", text_body="Inactive text", is_active=False,
    )
    inactive = render_received(inactive_space, request_id=11)
    assert inactive["subject"] == f"{inactive_space.name} request received"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_hardware_requester_email_uses_renderer_and_template_override(
    django_capture_on_commit_callbacks,
):
    reset_outbox()
    makerspace = make_space("template-hw-requester")
    product = make_product(makerspace)
    hardware_request = make_hardware_request(
        makerspace, product, contact_email="hw-requester@example.com"
    )

    with django_capture_on_commit_callbacks(execute=True):
        notifications.notify_request_accepted(hardware_request)
    assert mail.outbox[0].to == ["hw-requester@example.com"]
    assert mail.outbox[0].subject == f"{makerspace.name} request approved"
    assert "has been approved" in mail.outbox[0].body

    EmailTemplate.objects.create(
        makerspace=makerspace, key="hw_request_accepted",
        subject="Custom accepted {{ request_id }}",
        text_body="Custom accepted body",
        html_body="<p>Custom accepted body</p>",
    )
    reset_outbox()

    with django_capture_on_commit_callbacks(execute=True):
        notifications.notify_request_accepted(hardware_request)

    assert mail.outbox[0].subject == f"Custom accepted {hardware_request.id}"
    assert "Custom accepted body" in mail.outbox[0].body


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_hardware_staff_email_has_html_alternative():
    reset_outbox()
    makerspace = make_space("template-hw-staff")
    make_member(
        "template-hw-staff-manager", makerspace,
        membership_role=MakerspaceMembership.Role.SPACE_MANAGER,
    )
    hardware_request = make_hardware_request(makerspace, make_product(makerspace))

    # sync=True delivers inline so the return count is truthful and the message
    # lands in the outbox immediately (no transaction-commit hook needed).
    assert staff_notifications.send_staff_hardware_email(
        hardware_request, "submitted", sync=True
    )

    assert len(mail.outbox) == 1
    message_html(mail.outbox[0])


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_print_requester_recipient_prefers_contact_email_then_requester_email(
    django_capture_on_commit_callbacks,
):
    reset_outbox()
    makerspace = make_space("template-print-recipient")
    bucket = make_bucket(makerspace)
    requester = make_print_user("template-print-recipient-user", access_status="active")
    with_contact = make_print_request(bucket, requester)
    with_contact.contact_email = "buyer@example.com"
    with_contact.save(update_fields=["contact_email", "updated_at"])
    without_contact = make_print_request(bucket, requester)

    with django_capture_on_commit_callbacks(execute=True):
        print_emails.send_print_email("submitted", with_contact)
        print_emails.send_print_email("submitted", without_contact)

    assert [message.to for message in mail.outbox] == [
        ["buyer@example.com"],
        [requester.email],
    ]


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_authenticated_print_submit_emails_requester_and_staff(
    django_capture_on_commit_callbacks,
):
    reset_outbox()
    assert print_views_requests.queue_print_email is print_emails.queue_print_email
    makerspace = make_space("template-print-auth-submit")
    bucket = make_bucket(makerspace)
    requester = make_print_user("template-print-auth-user", access_status="active")
    staff = make_print_manager("template-print-auth-manager", makerspace)

    with django_capture_on_commit_callbacks(execute=True):
        response = print_authenticated_client(requester).post(
            print_request_list_url(),
            {"bucket": bucket.id, "title": "Authenticated bracket", "quantity": 1},
            format="json",
        )

    assert response.status_code == 201
    recipients = [address for message in mail.outbox for address in message.to]
    assert requester.email in recipients
    assert staff.email in recipients
    requester_email = next(message for message in mail.outbox if requester.email in message.to)
    staff_email = next(message for message in mail.outbox if staff.email in message.to)
    assert "received your makerspace print request" in requester_email.subject
    message_html(staff_email)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_print_price_privacy_is_unchanged_in_requester_email(
    django_capture_on_commit_callbacks,
):
    reset_outbox()
    makerspace = make_space("template-print-cash")
    bucket = make_bucket(makerspace)
    requester = make_print_user("template-print-cash-user", access_status="active")
    manager = make_print_manager("template-print-cash-manager", makerspace)
    print_request = make_print_request(bucket, requester, title="Bracket")
    print_workflow.accept(print_request, manager, price=Decimal("10.00"))
    print_request.refresh_from_db()
    reset_outbox()

    with django_capture_on_commit_callbacks(execute=True):
        print_emails.send_print_email("accepted", print_request)

    rendered = "\n".join(
        [mail.outbox[0].subject, mail.outbox[0].body, message_html(mail.outbox[0])]
    ).lower()
    assert "10.00" not in rendered
    assert "price" not in rendered
    assert "payment" not in rendered
    assert "paid" not in rendered


def test_blank_html_override_sends_text_only_not_default_html():
    # A custom override with a BLANK html_body is an intentional "text-only" choice and
    # must NOT silently fall back to the registry's default branded HTML.
    makerspace = make_space("template-blank-html")
    EmailTemplate.objects.create(
        makerspace=makerspace,
        key="hw_request_accepted",
        subject="Plain approval {{ request_id }}",
        text_body="Approved by {{ makerspace_name }}.",
        html_body="",
    )

    rendered = render_email_template(
        makerspace,
        "hw_request_accepted",
        {"request_id": "7", "makerspace_name": "Space"},
    )

    assert rendered["subject"] == "Plain approval 7"
    assert rendered["text_body"] == "Approved by Space."
    assert rendered["html_body"] == ""


def test_migration_translates_legacy_template_syntax():
    from importlib import import_module

    migration = import_module(
        "apps.integrations.migrations.0003_migrate_hardware_templates"
    )
    translate = migration._translate_legacy

    assert translate("Request #{{ request.id }}") == "Request #{{ request_id }}"
    assert translate("{{ makerspace.name }} hi") == "{{ makerspace_name }} hi"
    assert translate("Status: {{ request.status }}") == "Status: {{ status }}"
    # The known optional blocks map onto the flat block vars (no dangling label).
    assert (
        translate("Done.{% if request.return_due_at %}\n\nReturn by: {{ request.return_due_at }}{% endif %}")
        == "Done.{{ return_due_block }}"
    )
    assert (
        translate("No.{% if request.rejection_reason %}\n\nReason: {{ request.rejection_reason }}{% endif %}")
        == "No.{{ reason_block }}"
    )
    # Other block tags are stripped (inner text kept) and unmappable dotted tokens dropped;
    # no raw Django syntax survives.
    out = translate("{{ request.requester_username }}{% if x %}y{% endif %}")
    assert out == "y"
    assert "{%" not in out and "{{ request." not in out


def test_email_layout_save_rejects_layout_missing_content_slot():
    from django.core.exceptions import ValidationError

    makerspace = make_space("layout-model-guard")
    with pytest.raises(ValidationError):
        EmailLayout.objects.create(makerspace=makerspace, html="<div>no slot</div>")
    # Blank layout html is allowed (renderer falls back to the default layout).
    EmailLayout.objects.create(makerspace=make_space("layout-model-blank"), html="")


def test_rendered_subject_is_single_line():
    # A multiline merge var in the subject must not produce embedded newlines (Django
    # BadHeaderError would otherwise drop the email).
    makerspace = make_space("template-subject-newline")
    EmailTemplate.objects.create(
        makerspace=makerspace,
        key="hw_request_accepted",
        subject="Approved {{ return_due_block }}",
        text_body="body",
    )
    rendered = render_email_template(
        makerspace,
        "hw_request_accepted",
        {"return_due_block": "\n\nReturn by: 2026-06-30"},
    )
    assert "\n" not in rendered["subject"]
    assert rendered["subject"] == "Approved Return by: 2026-06-30"
