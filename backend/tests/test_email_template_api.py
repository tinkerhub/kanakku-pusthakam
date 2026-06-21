import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.integrations import email_registry
from apps.makerspaces.models import MakerspaceMembership
from tests.return_helpers import (
    authenticated_client,
    make_member,
    make_space,
    make_user,
)

pytestmark = pytest.mark.django_db


def template_list_url(makerspace):
    return reverse("admin-email-templates", kwargs={"makerspace_id": makerspace.id})


def template_detail_url(makerspace, key):
    return reverse(
        "admin-email-template-detail",
        kwargs={"makerspace_id": makerspace.id, "key": key},
    )


def layout_url(makerspace):
    return reverse("admin-email-layout", kwargs={"makerspace_id": makerspace.id})


def preview_url(makerspace, key):
    return reverse(
        "admin-email-template-preview",
        kwargs={"makerspace_id": makerspace.id, "key": key},
    )


def make_inventory_manager(username, makerspace):
    return make_member(
        username,
        makerspace,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
        role=User.Role.REQUESTER,
    )


def make_print_manager(username, makerspace):
    return make_member(
        username,
        makerspace,
        membership_role=MakerspaceMembership.Role.PRINT_MANAGER,
        role=User.Role.REQUESTER,
    )


def make_superadmin(username):
    return make_user(
        username,
        role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
        is_superuser=True,
    )


def returned_keys(response):
    return {row["key"] for row in response.data}


def test_list_filters_to_role_editable_keys():
    makerspace = make_space("email-template-list")
    space_manager = make_member("email-template-list-space", makerspace)
    inventory_manager = make_inventory_manager("email-template-list-inventory", makerspace)
    print_manager = make_print_manager("email-template-list-print", makerspace)
    superadmin = make_superadmin("email-template-list-super")

    space_keys = returned_keys(
        authenticated_client(space_manager).get(template_list_url(makerspace))
    )
    inventory_keys = returned_keys(
        authenticated_client(inventory_manager).get(template_list_url(makerspace))
    )
    print_keys = returned_keys(
        authenticated_client(print_manager).get(template_list_url(makerspace))
    )
    superadmin_response = authenticated_client(superadmin).get(
        template_list_url(makerspace)
    )
    superadmin_keys = returned_keys(superadmin_response)

    assert {"hw_request_accepted", "print_accepted"} <= space_keys
    assert "hw_request_accepted" in inventory_keys
    assert not any(key.startswith("print_") for key in inventory_keys)
    assert "print_accepted" in print_keys
    assert not any(key.startswith("hw_") for key in print_keys)
    assert len(superadmin_keys) == 27


def test_get_and_put_template_override_roundtrip():
    makerspace = make_space("email-template-roundtrip")
    inventory_manager = make_inventory_manager("email-template-roundtrip-user", makerspace)
    client = authenticated_client(inventory_manager)
    payload = {
        "subject": "Custom {{ request_id }}",
        "text_body": "Body {{ makerspace_name }}",
        "html_body": "<p>Hi</p>",
    }

    updated = client.put(
        template_detail_url(makerspace, "hw_request_accepted"),
        payload,
        format="json",
    )
    retrieved = client.get(template_detail_url(makerspace, "hw_request_accepted"))
    listed = client.get(template_list_url(makerspace))
    listed_row = next(
        row for row in listed.data if row["key"] == "hw_request_accepted"
    )

    assert updated.status_code == 200
    assert updated.data["is_customized"] is True
    assert updated.data["subject"] == payload["subject"]
    assert retrieved.status_code == 200
    assert retrieved.data["subject"] == payload["subject"]
    assert retrieved.data["is_customized"] is True
    assert listed_row["is_customized"] is True


def test_put_printing_key_as_inventory_manager_is_forbidden():
    makerspace = make_space("email-template-inventory-forbidden")
    inventory_manager = make_inventory_manager(
        "email-template-inventory-forbidden-user",
        makerspace,
    )

    response = authenticated_client(inventory_manager).put(
        template_detail_url(makerspace, "print_accepted"),
        {
            "subject": "Custom",
            "text_body": "Body",
            "html_body": "<p>Body</p>",
        },
        format="json",
    )

    assert response.status_code == 403


def test_unknown_key_returns_404():
    makerspace = make_space("email-template-unknown")
    space_manager = make_member("email-template-unknown-manager", makerspace)

    response = authenticated_client(space_manager).get(
        template_detail_url(makerspace, "not_a_real_key")
    )

    assert response.status_code == 404


def test_makerspace_without_role_returns_404():
    own_space = make_space("email-template-own")
    other_space = make_space("email-template-other")
    space_manager = make_member("email-template-own-manager", own_space)
    client = authenticated_client(space_manager)

    listed = client.get(template_list_url(other_space))
    detailed = client.get(template_detail_url(other_space, "hw_request_accepted"))

    assert listed.status_code == 404
    assert detailed.status_code == 404


def test_delete_resets_override():
    makerspace = make_space("email-template-delete")
    inventory_manager = make_inventory_manager("email-template-delete-user", makerspace)
    client = authenticated_client(inventory_manager)
    url = template_detail_url(makerspace, "hw_request_accepted")
    default_subject = email_registry.EMAIL_TEMPLATES["hw_request_accepted"][
        "default_subject"
    ]

    updated = client.put(
        url,
        {
            "subject": "Temporary custom subject",
            "text_body": "Temporary body",
            "html_body": "<p>Temporary</p>",
        },
        format="json",
    )
    deleted = client.delete(url)
    retrieved = client.get(url)

    assert updated.status_code == 200
    assert deleted.status_code == 204
    assert retrieved.status_code == 200
    assert retrieved.data["is_customized"] is False
    assert retrieved.data["subject"] == default_subject


def test_layout_requires_manage_makerspace():
    makerspace = make_space("email-layout-role")
    space_manager = make_member("email-layout-role-space", makerspace)
    inventory_manager = make_inventory_manager("email-layout-role-inventory", makerspace)
    superadmin = make_superadmin("email-layout-role-super")

    space_client = authenticated_client(space_manager)
    default_layout = space_client.get(layout_url(makerspace))
    updated = space_client.put(
        layout_url(makerspace),
        {"html": "<div>BRAND {{ content }}</div>", "is_active": True},
        format="json",
    )
    inventory_layout = authenticated_client(inventory_manager).get(layout_url(makerspace))
    superadmin_layout = authenticated_client(superadmin).get(layout_url(makerspace))

    assert default_layout.status_code == 200
    assert default_layout.data["is_default"] is True
    assert updated.status_code == 200
    assert updated.data["is_default"] is False
    assert inventory_layout.status_code == 404
    assert superadmin_layout.status_code == 200


def test_layout_put_sanitizes_html():
    makerspace = make_space("email-layout-sanitize")
    space_manager = make_member("email-layout-sanitize-manager", makerspace)
    client = authenticated_client(space_manager)

    updated = client.put(
        layout_url(makerspace),
        {
            "html": "<div>{{ content }}<script>alert(1)</script></div>",
            "is_active": True,
        },
        format="json",
    )
    retrieved = client.get(layout_url(makerspace))

    assert updated.status_code == 200
    assert "<script" not in retrieved.data["html"].lower()


def test_template_put_sanitizes_html():
    makerspace = make_space("email-template-sanitize")
    space_manager = make_member("email-template-sanitize-manager", makerspace)
    client = authenticated_client(space_manager)

    updated = client.put(
        template_detail_url(makerspace, "hw_request_accepted"),
        {
            "subject": "Custom {{ request_id }}",
            "text_body": "Body {{ makerspace_name }}",
            "html_body": "<p>ok</p><script>bad()</script>",
        },
        format="json",
    )
    retrieved = client.get(template_detail_url(makerspace, "hw_request_accepted"))

    assert updated.status_code == 200
    assert "<script" not in retrieved.data["html_body"].lower()


def test_preview_returns_sample_rendered():
    makerspace = make_space("email-template-preview")
    space_manager = make_member("email-template-preview-space", makerspace)
    inventory_manager = make_inventory_manager("email-template-preview-inventory", makerspace)
    title_sample = next(
        variable["sample"]
        for variable in email_registry.EMAIL_TEMPLATES["print_accepted"]["variables"]
        if variable["name"] == "title"
    )

    preview = authenticated_client(space_manager).post(
        preview_url(makerspace, "print_accepted"),
        {},
        format="json",
    )
    forbidden = authenticated_client(inventory_manager).post(
        preview_url(makerspace, "print_accepted"),
        {},
        format="json",
    )

    assert preview.status_code == 200
    assert preview.data["subject"]
    assert preview.data["text_body"]
    assert preview.data["html_body"]
    assert title_sample in preview.data["html_body"]
    assert "<script" not in preview.data["html_body"].lower()
    assert forbidden.status_code == 403


def test_layout_without_content_slot_is_rejected():
    makerspace = make_space("email-layout-no-slot")
    space_manager = make_member("email-layout-no-slot-mgr", makerspace)
    client = authenticated_client(space_manager)

    response = client.put(
        layout_url(makerspace),
        {"html": "<div>no slot here</div>", "is_active": True},
        format="json",
    )

    assert response.status_code == 400
    # A blank layout is still allowed (the renderer falls back to the default layout).
    ok = client.put(layout_url(makerspace), {"html": "", "is_active": True}, format="json")
    assert ok.status_code == 200


def test_preview_renders_unsaved_draft_content():
    makerspace = make_space("email-preview-draft")
    space_manager = make_member("email-preview-draft-mgr", makerspace)
    client = authenticated_client(space_manager)

    response = client.post(
        preview_url(makerspace, "print_accepted"),
        {"subject": "Draft {{ title }}", "text_body": "draft body", "html_body": ""},
        format="json",
    )

    assert response.status_code == 200
    sample_title = next(
        v["sample"]
        for v in email_registry.EMAIL_TEMPLATES["print_accepted"]["variables"]
        if v["name"] == "title"
    )
    assert response.data["subject"] == f"Draft {sample_title}"
    assert response.data["text_body"] == "draft body"
    assert response.data["html_body"] == ""
