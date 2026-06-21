import re

import nh3
from django.utils.html import escape


ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "a",
    "h1",
    "h2",
    "h3",
    "div",
    "span",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "hr",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}
URL_SCHEMES = {"https", "http", "mailto"}

PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

DEFAULT_LAYOUT_HTML = """
<div>
  <table>
    <tbody>
      <tr><td><h2>Makerspace</h2></td></tr>
      <tr><td><div>{{ content }}</div></td></tr>
      <tr><td><hr><p>Makerspace notifications</p></td></tr>
    </tbody>
  </table>
</div>
"""


def sanitize_email_html(html: str) -> str:
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=URL_SCHEMES,
    )


def render_email_template(makerspace, key, variables: dict):
    from apps.integrations.email_models import EmailTemplate
    from apps.integrations.email_registry import get_template

    registry_entry = get_template(key)
    override = EmailTemplate.objects.filter(
        makerspace=makerspace,
        key=key,
        is_active=True,
    ).first()

    if override:
        # An override always carries subject/text (the write serializer requires them);
        # fall back only as a defensive guard. html_body is the meaningful exception:
        # a BLANK override html_body is an intentional "text-only" choice, so it must
        # NOT silently revert to the default branded HTML.
        subject_source = override.subject or registry_entry["default_subject"]
        text_source = override.text_body or registry_entry["default_text"]
        html_source = override.html_body
    else:
        subject_source = registry_entry["default_subject"]
        text_source = registry_entry["default_text"]
        html_source = registry_entry["default_html"]

    return _render(makerspace, registry_entry, subject_source, text_source, html_source, variables)


def render_email_preview(
    makerspace,
    key,
    variables: dict,
    subject=None,
    text_body=None,
    html_body=None,
):
    """Render UNSAVED editor draft fields (falling back to registry defaults for any
    omitted/blank subject/text). A provided html_body of "" means intentional text-only;
    an OMITTED html_body (None) falls back to the registry default."""
    from apps.integrations.email_registry import get_template

    registry_entry = get_template(key)
    subject_source = subject if (subject and subject.strip()) else registry_entry["default_subject"]
    text_source = text_body if (text_body and text_body.strip()) else registry_entry["default_text"]
    html_source = html_body if html_body is not None else registry_entry["default_html"]
    return _render(makerspace, registry_entry, subject_source, text_source, html_source, variables)


def _render(makerspace, registry_entry, subject_source, text_source, html_source, variables):
    from apps.integrations.email_models import EmailLayout

    # Subjects MUST be single-line: Django raises BadHeaderError on embedded CR/LF, and the
    # send sites catch-and-drop, so a multiline merge var (e.g. {{ return_due_block }}) in a
    # subject would silently suppress the whole email. Collapse all whitespace to spaces.
    subject = " ".join(_render_text(subject_source, variables).split())
    text_body = _render_text(text_source, variables)
    if not html_source.strip():
        return {"subject": subject, "text_body": text_body, "html_body": ""}

    trusted_html = {
        item["name"]: item.get("trusted_html", False)
        for item in registry_entry["variables"]
    }
    rendered_html = _render_html(html_source, variables, trusted_html)
    layout = EmailLayout.objects.filter(
        makerspace=makerspace,
        is_active=True,
    ).first()
    layout_html = (
        layout.html
        if layout and layout.html.strip()
        else DEFAULT_LAYOUT_HTML
    )
    wrapped_html = layout_html.replace("{{ content }}", rendered_html)
    return {
        "subject": subject,
        "text_body": text_body,
        "html_body": sanitize_email_html(wrapped_html),
    }


def _render_text(template, variables):
    return PLACEHOLDER_RE.sub(
        lambda match: str(variables.get(match.group(1), "")),
        template,
    )


def _render_html(template, variables, trusted_html):
    def replace(match):
        name = match.group(1)
        value = str(variables.get(name, ""))
        return value if trusted_html.get(name, False) else escape(value)

    return PLACEHOLDER_RE.sub(replace, template)
