ACTION = "MANAGE_PRINTING"

VAR_META = {
    "makerspace_name": ("Makerspace name", "TinkerSpace Calicut", False),
    "requester_display_name": ("Requester display name", "Shaans", False),
    "title": ("Print request title", "Robotics chassis", False),
    "bucket_name": ("Print bucket name", "General prints", False),
    "public_token": ("Public tracking token", "4f8c8f40-7f3d-4f5e-9dc2-5f8140f7cafe", False),
    "status_link_block": ("Optional tracking link text block", "\nTrack your request: https://example.test", False),
    "status_link_block_html": ("Rendered tracking link block", "<p>Track: <a href=\"https://example.test\">link</a></p>", True),
    "reason_block": ("Optional rejection reason text block", "Reason: Unsupported material", False),
    "request_id": ("Print request ID", "77", False),
    "staff_summary": ("Staff-facing print request summary", "Status: accepted\nTitle: Bracket", False),
    "staff_summary_html": ("Rendered staff-facing print summary", "<ul><li>Status: accepted</li></ul>", True),
}


def _vars(*names):
    return [
        {
            "name": name,
            "description": VAR_META[name][0],
            "sample": VAR_META[name][1],
            "trusted_html": VAR_META[name][2],
        }
        for name in names
    ]


def _entry(audience, label, variables, subject, text, html):
    return {
        "family": "printing",
        "audience": audience,
        "action": ACTION,
        "label": label,
        "variables": variables,
        "default_subject": subject,
        "default_text": text,
        "default_html": html,
    }


def _requester(label, subject, greeting, status_text, include_reason=False):
    names = [
        "makerspace_name",
        "title",
        "bucket_name",
        "status_link_block",
        "status_link_block_html",
        "public_token",
    ]
    if "requester_display_name" in greeting:
        names.insert(1, "requester_display_name")
    if include_reason:
        names.append("reason_block")
    hello = f"Hello {greeting}," if greeting else "Hello,"
    text = (
        f"{hello}\n\n"
        f'{status_text}\n\n'
    )
    html = f"<p>{hello}</p><p>{status_text}</p>"
    if include_reason:
        text += "{{ reason_block }}\n\n"
        html += "<p>{{ reason_block }}</p>"
    text += (
        "Bucket: {{ bucket_name }}\n"
        "Makerspace: {{ makerspace_name }}\n"
    )
    html += "<p>Bucket: {{ bucket_name }}<br>Makerspace: {{ makerspace_name }}</p>"
    text += "{{ status_link_block }}\nTracking token: {{ public_token }}\n"
    html += "{{ status_link_block_html }}<p>Tracking token: <strong>{{ public_token }}</strong></p>"
    return _entry("requester", label, _vars(*names), subject, text, html)


def _staff(label, subject, event):
    text = f"Print request #{{{{ request_id }}}} {event}.\n\n{{{{ staff_summary }}}}"
    html = f"<p>Print request #{{{{ request_id }}}} {event}.</p><div>{{{{ staff_summary_html }}}}</div>"
    return _entry(
        "staff",
        label,
        _vars("makerspace_name", "request_id", "staff_summary", "staff_summary_html"),
        subject,
        text,
        html,
    )


PRINTING_TEMPLATES = {
    "print_submitted": _requester(
        "Print request submitted",
        "We received your makerspace print request",
        "",
        (
            "We've received your print request \"{{ title }}\".\n\n"
            "We'll email you again when its status changes. "
            "You can also track it with your request link."
        ),
    ),
    "print_accepted": _requester(
        "Print request accepted",
        "Your makerspace print request was accepted",
        "{{ requester_display_name }}",
        "Your print request \"{{ title }}\" has been accepted.",
    ),
    "print_started": _requester(
        "Print request started",
        "Your makerspace print request is now printing",
        "",
        (
            "Your print request \"{{ title }}\" is now printing.\n\n"
            "We'll let you know when it's ready to collect."
        ),
    ),
    "print_completed": _requester(
        "Print request completed",
        "Your makerspace print request is ready to collect",
        "{{ requester_display_name }}",
        "Your print request \"{{ title }}\" is complete.",
    ),
    "print_rejected": _requester(
        "Print request rejected",
        "Your makerspace print request was rejected",
        "{{ requester_display_name }}",
        "Your print request \"{{ title }}\" has been rejected.",
        include_reason=True,
    ),
    "print_staff_submitted": _staff(
        "Staff print request submitted",
        "{{ makerspace_name }} print request #{{ request_id }} submitted",
        "submitted",
    ),
    "print_staff_accepted": _staff(
        "Staff print request accepted",
        "{{ makerspace_name }} print request #{{ request_id }} accepted",
        "accepted",
    ),
    "print_staff_started": _staff(
        "Staff print request started",
        "{{ makerspace_name }} print request #{{ request_id }} started",
        "started",
    ),
    "print_staff_completed": _staff(
        "Staff print request completed",
        "{{ makerspace_name }} print request #{{ request_id }} completed",
        "completed",
    ),
    "print_staff_rejected": _staff(
        "Staff print request rejected",
        "{{ makerspace_name }} print request #{{ request_id }} rejected",
        "rejected",
    ),
    "print_staff_failed": _staff(
        "Staff print request failed",
        "{{ makerspace_name }} print request #{{ request_id }} failed",
        "failed",
    ),
    "print_staff_collected": _staff(
        "Staff print request collected",
        "{{ makerspace_name }} print request #{{ request_id }} collected",
        "collected",
    ),
    "print_staff_reprinted": _staff(
        "Staff print request reprinted",
        "{{ makerspace_name }} reprint request #{{ request_id }} accepted",
        "accepted",
    ),
}
