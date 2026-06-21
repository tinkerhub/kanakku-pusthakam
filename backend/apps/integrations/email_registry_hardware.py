ACTION = "EDIT_INVENTORY"

VAR_META = {
    "makerspace_name": ("Makerspace name", "TinkerSpace Calicut", False),
    "request_id": ("Hardware request ID", "42", False),
    "status": ("Current request status", "pending_approval", False),
    "return_due_block": ("Optional return due text block", "\n\nReturn by: 2026-06-30", False),
    "reason_block": ("Optional rejection reason text block", "\n\nReason: Out of stock", False),
    "item_list_html": ("Rendered requested item list", "<ul><li>Arduino Uno: 1</li></ul>", True),
    "staff_summary": ("Staff-facing request summary", "Status: accepted\nRequester: shaans", False),
    "staff_summary_html": ("Rendered staff-facing request summary", "<ul><li>Status: accepted</li></ul>", True),
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
        "family": "hardware",
        "audience": audience,
        "action": ACTION,
        "label": label,
        "variables": variables,
        "default_subject": subject,
        "default_text": text,
        "default_html": html,
    }


def _requester(label, subject_tail, text, html, *extra_vars):
    return _entry(
        "requester",
        label,
        _vars("makerspace_name", "request_id", "item_list_html", *extra_vars),
        "{{ makerspace_name }} " + subject_tail,
        text,
        html,
    )


def _staff(label, subject_tail, text):
    return _entry(
        "staff",
        label,
        _vars("makerspace_name", "request_id", "staff_summary", "staff_summary_html"),
        "{{ makerspace_name }} hardware request #{{ request_id }} " + subject_tail,
        text + "\n\n{{ staff_summary }}",
        "<p>" + text + "</p><div>{{ staff_summary_html }}</div>",
    )


HARDWARE_TEMPLATES = {
    "hw_request_received": _requester(
        "Hardware request received",
        "request received",
        (
            "Your makerspace request #{{ request_id }} was received.\n\n"
            "Status: {{ status }}\n"
            "Use your email or phone on the public request page to check status."
        ),
        (
            "<p>Your makerspace request #{{ request_id }} was received.</p>"
            "<p>Status: {{ status }}</p>"
            "<p>Use your email or phone on the public request page to check status.</p>"
            "<div>{{ item_list_html }}</div>"
        ),
        "status",
    ),
    "hw_request_accepted": _requester(
        "Hardware request accepted",
        "request approved",
        "Your makerspace request #{{ request_id }} has been approved.{{ return_due_block }}",
        (
            "<p>Your makerspace request #{{ request_id }} has been approved.</p>"
            "<p>{{ return_due_block }}</p><div>{{ item_list_html }}</div>"
        ),
        "return_due_block",
    ),
    "hw_request_rejected": _requester(
        "Hardware request rejected",
        "request rejected",
        "Your makerspace request #{{ request_id }} was rejected.{{ reason_block }}",
        (
            "<p>Your makerspace request #{{ request_id }} was rejected.</p>"
            "<p>{{ reason_block }}</p><div>{{ item_list_html }}</div>"
        ),
        "reason_block",
    ),
    "hw_request_issued": _requester(
        "Hardware request issued",
        "request issued",
        (
            "Your approved makerspace request #{{ request_id }} has been handed out."
            "{{ return_due_block }}"
        ),
        (
            "<p>Your approved makerspace request #{{ request_id }} has been handed out.</p>"
            "<p>{{ return_due_block }}</p><div>{{ item_list_html }}</div>"
        ),
        "return_due_block",
    ),
    "hw_request_returned": _requester(
        "Hardware request returned",
        "request returned",
        "Your makerspace request #{{ request_id }} has been returned and closed.",
        (
            "<p>Your makerspace request #{{ request_id }} has been returned and closed.</p>"
            "<div>{{ item_list_html }}</div>"
        ),
    ),
    "hw_return_reminder": _requester(
        "Hardware return reminder",
        "return reminder",
        "Your makerspace request #{{ request_id }} is due for return.{{ return_due_block }}",
        (
            "<p>Your makerspace request #{{ request_id }} is due for return.</p>"
            "<p>{{ return_due_block }}</p><div>{{ item_list_html }}</div>"
        ),
        "return_due_block",
    ),
    "hw_staff_submitted": _staff(
        "Staff hardware request submitted",
        "submitted",
        "A new hardware request needs review.",
    ),
    "hw_staff_accepted": _staff(
        "Staff hardware request accepted",
        "accepted",
        "Hardware request #{{ request_id }} was accepted.",
    ),
    "hw_staff_rejected": _staff(
        "Staff hardware request rejected",
        "rejected",
        "Hardware request #{{ request_id }} was rejected.",
    ),
    "hw_staff_issued": _staff(
        "Staff hardware request issued",
        "issued",
        "Hardware request #{{ request_id }} was issued.",
    ),
    "hw_staff_partially_returned": _staff(
        "Staff hardware request partially returned",
        "partially returned",
        "Hardware request #{{ request_id }} was partially returned.",
    ),
    "hw_staff_returned": _staff(
        "Staff hardware request returned",
        "returned",
        "Hardware request #{{ request_id }} was fully returned and closed.",
    ),
    "hw_staff_closed_with_issue": _staff(
        "Staff hardware request closed with issue",
        "closed with issue",
        "Hardware request #{{ request_id }} was closed with damaged or missing items.",
    ),
    "hw_staff_return_reminder": _staff(
        "Staff hardware return reminder",
        "return reminder",
        "Hardware request #{{ request_id }} is due for return.",
    ),
}
