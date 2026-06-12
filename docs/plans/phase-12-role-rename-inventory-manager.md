# Phase 12 — Role rename (Admin → Space Manager) + new Inventory Manager role

**Status:** Stage 1 plan, rev 2 (post Codex review). Pending Codex re-review + user approval.

## Goal

1. Rename the **Admin** role to **Space Manager** everywhere — stored enum value
   (`admin` → `space_manager`), human label, code references, URLs, and existing DB
   rows (data migration). Pure rename: no permission change.
2. Add a new **Inventory Manager** role (per-makerspace, membership-only) that "deals
   all hardware": the full hardware lifecycle, but **not** printing, staff management,
   or makerspace settings.
3. **Super Admin**, **Print Manager**, **Guest Admin** unchanged.

## Decisions (locked with user)

- Rename depth: enum value + label + data migration + all refs.
- Guest Admin: unchanged.
- Inventory Manager actions: `view_inventory, edit_inventory, accept_request,
  reject_request, assign_box, issue_request, return_request, upload_evidence,
  manage_qr, view_audit`. **Excludes** `manage_printing, manage_staff,
  manage_makerspace, transfer_stock`.
- Space Manager keeps **all** current Admin powers.

## Decisions (resolved during Codex review — rev 2)

- **Inventory Manager is membership-only** (a `MakerspaceMembership.Role`, like Print
  Manager). It is **not** added to `User.Role` or `STAFF_ROLES`. Rationale: adding a
  global role would (a) couple a per-makerspace concept into a global scalar and (b)
  break on existing-user promotion, since `_global_role_for_membership` only sets
  `user.role` on user *creation*, not on promoting an existing requester
  (`admin_api/views.py:210-224`). Their global `User.role` stays `requester`.
- Because Inventory Manager has no global staff role, the **evidence gates must move
  from the global `STAFF_ROLES` (`IsStaff`) to membership-action + active-status
  checks** — consistent with every other hardware endpoint. This also fixes a latent
  over-broad scoping bug in `EvidenceDetailView`.
- **Delegation:** a Space Manager (holding `MANAGE_MAKERSPACE`) may create **Inventory
  Manager** and **Print Manager** memberships in their own makerspace; only a
  superadmin may create Space Managers / Guest Admins. (Real requirement, not "TBD".)

## Load-bearing design facts (from code audit)

- Roles live in **two** enums: `User.Role` (global) and `MakerspaceMembership.Role`
  (per-makerspace — the one `rbac.py` keys authority on).
- Hardware endpoints (`accept/reject/assign-box/issue/return`, queues) already gate on
  **membership** via `rbac.makerspaces_for_action()` + their own active-status check
  (`hardware_requests/permissions.py`).
- The **only** outliers are the **evidence** endpoints, which gate on the global
  `STAFF_ROLES` via `IsStaff` (`apps/evidence/views.py:37-39`, `:100-101`). Bringing
  them in line with the membership pattern is what lets a membership-only role work.
- `rbac.can()` / `rbac.makerspaces_for_action()` **ignore `access_status`**. Gates that
  call them directly without an active check let suspended/restricted members through —
  notably the QR endpoints (`boxes/api_views.py:26-29`). Inventory Manager uses QR, so
  this is folded in.
- The data migration touches **only the `role` columns**. Infrastructure named "admin"
  — Django admin, the `admin_api` app, the `/api/v1/admin/` URL prefix, the `/admin`
  frontend route, `is_superuser`, `admin-*` URL names, `ADMIN_DIRECT` in
  `self_checkout_models.py:8`, the OpenAPI sample username (`openapi.py:93`) — is **not**
  the role and stays unchanged.

## Backend changes

### Models
- `apps/accounts/models.py:8` `User.Role`: rename only `ADMIN = "admin","Admin"` →
  `SPACE_MANAGER = "space_manager","Space Manager"`. **No** `INVENTORY_MANAGER` here.
- `apps/makerspaces/models.py:78,93` `MakerspaceMembership.Role`: rename `ADMIN` →
  `SPACE_MANAGER`; add `INVENTORY_MANAGER = "inventory_manager","Inventory Manager"`;
  change field `default=Role.ADMIN` → `default=Role.SPACE_MANAGER`.

### RBAC (`apps/accounts/rbac.py`)
- Rename `_ADMIN_ACTIONS` → `_SPACE_MANAGER_ACTIONS` (contents unchanged).
- Add `_INVENTORY_MANAGER_ACTIONS = {VIEW_INVENTORY, EDIT_INVENTORY, ACCEPT_REQUEST,
  REJECT_REQUEST, ASSIGN_BOX, ISSUE_REQUEST, RETURN_REQUEST, UPLOAD_EVIDENCE,
  MANAGE_QR, VIEW_AUDIT}`.
- `_MEMBERSHIP_ROLE_ACTIONS` (line 61): `{SPACE_MANAGER: _SPACE_MANAGER_ACTIONS,
  GUEST_ADMIN: _GUEST_ADMIN_ACTIONS, INVENTORY_MANAGER: _INVENTORY_MANAGER_ACTIONS,
  PRINT_MANAGER: _PRINT_MANAGER_ACTIONS}`.
- Superadmin checks unchanged. (`can()` / `makerspaces_for_action()` still ignore
  access_status by design — callers add the active check; see gate changes below.)

### Permissions
- `apps/accounts/permissions.py:8`: `STAFF_ROLES` — rename `ADMIN` → `SPACE_MANAGER`
  only. Do **not** add Inventory Manager (it's membership-only).
- `HasMakerspaceAction` (`apps/accounts/permissions.py:40-54`): add an active-status
  check (`user.access_status == ACTIVE`) before `rbac.can()`, so any view using it is
  suspended-safe. (Used by evidence upload below.)

### Evidence gates (`apps/evidence/views.py`) — make membership-driven
- `EvidenceUploadUrlView` (:37-39): set `permission_classes = [IsAuthenticated,
  HasMakerspaceAction]` (drop `IsStaff`); ensure `required_action = Action.UPLOAD_EVIDENCE`
  is set so the membership check applies. Keeps superadmin (rbac.can True) and
  guest_admin/space_manager working; enables Inventory Manager; blocks suspended users
  via the new active check.
- `EvidenceDetailView` (:100-101): replace bare `IsStaff` + broad
  `scope_by_makerspace` with active-authenticated + `scope_by_action(request.user,
  Action.UPLOAD_EVIDENCE, qs)` so detail is scoped to the evidence permission, not "any
  membership". Fixes the pre-existing over-broad read.

### QR gate active-status fix (`apps/boxes/api_views.py:26-29`)
- `_require_qr` / `QrPermissionMixin`: add the active-status check alongside the
  existing `rbac.can(..., MANAGE_QR, ...)` so suspended members can't manage QR. (Now
  load-bearing because Inventory Manager holds `manage_qr`.)

### admin_api
- `views.py:235-240` `_global_role_for_membership`: SPACE_MANAGER→`User.Role.SPACE_MANAGER`,
  GUEST_ADMIN→`GUEST_ADMIN`, **INVENTORY_MANAGER→`REQUESTER`** (membership-only, mirrors
  print_manager), else `REQUESTER`.
- `views.py:243-248` `_can_create_staff_role`: superadmin → any; non-superadmin with
  `MANAGE_MAKERSPACE` → may create `PRINT_MANAGER` **and** `INVENTORY_MANAGER` in their
  makerspace.
- `views.py:177-198` `StaffListCreateView.get_queryset`: extend the non-ALL scope
  branch so both `PRINT_MANAGER` **and** `INVENTORY_MANAGER` are listable by a space
  manager scoped via `MANAGE_MAKERSPACE`.
- `serializers.py:141` role-choice allowlist: add `INVENTORY_MANAGER`, rename
  `ADMIN`→`SPACE_MANAGER`.
- `urls.py:41-44`: rename path `users/admins` → `users/space-managers` (name
  `admin-users-space-managers`, role `SPACE_MANAGER`); add `users/inventory-managers`
  (`admin-users-inventory-managers`, role `INVENTORY_MANAGER`); keep guest-admins/
  print-managers.

### Django-admin gates (literal "admin" role comparisons — rename only)
- `config/unfold.py:31`: `("superadmin","admin")` → `("superadmin","space_manager")`.
- `apps/apiclients/admin.py:20`, `apps/printing/admin.py:9`,
  `apps/hardware_requests/admin.py:8`: `MANAGER_ROLES = (SUPERADMIN, ADMIN)` →
  `(SUPERADMIN, SPACE_MANAGER)`. Inventory Manager is **not** added (no Django-admin
  access — consistent with guest/print).

### Migrations
- `apps/accounts/migrations/0004_rename_admin_to_space_manager.py` (depends on `0003`):
  `AlterField` `User.role` (choices: superadmin/space_manager/guest_admin/requester) +
  `RunPython` `filter(role="admin").update(role="space_manager")`. **Fully reversible**
  (reverse: `space_manager`→`admin`) — no new value introduced here.
- `apps/makerspaces/migrations/0008_rename_admin_role_add_inventory_manager.py`
  (depends on `0007`): `AlterField` `MakerspaceMembership.role` (choices +
  `default="space_manager"`) + `RunPython` forward `filter(role="admin")
  .update(role="space_manager")`. **Reverse policy (documented lossy):** map
  `space_manager`→`admin`, and downgrade any `inventory_manager`→`guest_admin` (closest
  surviving hardware role under the old choice set), so rollback never leaves an
  unknown enum value. Reverse runs *before* the choices revert.
- Do **not** edit historical migration choice strings.

## Frontend changes
- `features/staff/StaffPanels.tsx:230,241`: rename `/admin/users/admins` →
  `/admin/users/space-managers` ("Space managers"); add a card hitting
  `/admin/users/inventory-managers` ("Inventory managers"); keep guest/print.
- `features/staff/StaffApp.tsx:72,177`: cosmetic desk label "Admin" → "Space Manager".
  Role-based nav gating stays cosmetic (`guestOnly`); backend enforces authority.

## Out-of-scope interactions (acknowledged, not changed here)
- **Direct loans** (`direct_loan_views.py`) check `Action.ISSUE_REQUEST`, so Inventory
  Managers will *incidentally* gain direct-handout access — consistent with "they can
  issue". The direct-loan/self-checkout features remain flagged tech debt (they bypass
  `workflow.py`/`availability.py` and `direct_loan_views.py:79-81` lacks an
  active-status gate). Not modified in this phase.

## Tests
- **Comprehensive sweep** (not a fixed line list — replace *every* occurrence): in
  `backend/tests/`, replace `User.Role.ADMIN`→`User.Role.SPACE_MANAGER`,
  `MakerspaceMembership.Role.ADMIN`→`MakerspaceMembership.Role.SPACE_MANAGER`, and the
  literal role value `role="admin"` / `role: "admin"`→`"space_manager"`. After editing,
  grep the test tree for any surviving `Role.ADMIN` / `"admin"` *role* usage to confirm
  zero misses. Known occurrences include (non-exhaustive): `test_auth.py:20,29,37,150`;
  `test_audit.py:24,57,68`; `test_rbac.py:27,40,49,52,63,65,77,79,85,93,117`;
  `test_evidence.py:26,74,86,178,257`; `test_issue.py:39,40`; `return_helpers.py:31,32`;
  `test_printing.py:31,32,587,588`; `test_request_workflow.py:45,46`;
  `test_admin_direct_loans.py:21,27`; `test_memberships.py:33`;
  `test_apiclients.py:37,48`. (Leave Django-admin / `is_superuser` / `admin_api` /
  `/admin` references untouched — those are not the role.)
- New tests:
  - `test_rbac.py`: Inventory Manager grants the full hardware action set; denies
    `manage_printing/manage_staff/manage_makerspace`.
  - Issue/return: an Inventory Manager member (global `requester`) can assign-box,
    issue, **request an evidence-upload URL**, and return — proving the evidence gate
    no longer needs a global staff role.
  - Evidence: an **existing requester promoted** to Inventory Manager can upload
    evidence (the promotion-sync regression Codex flagged); a suspended member is
    blocked; `EvidenceDetailView` is scoped to `UPLOAD_EVIDENCE` (a member without it
    can't read others' evidence).
  - QR: a suspended Inventory Manager / Space Manager is denied `manage_qr`.
  - `test_admin_api.py`: create + list Inventory Manager via
    `users/inventory-managers`, makerspace-scoped; a Space Manager can delegate it;
    cross-tenant denied.
  - Migration: reverse downgrades `inventory_manager`→`guest_admin` (no orphan value).

## Docs
- Update `CLAUDE.md` and `docs/HANDOVER.md` role wording (Admin → Space Manager;
  document Inventory Manager as membership-only hardware role; note the evidence-gate
  change).

## Risks
- **Role-vs-infra "admin" confusion** — mitigated: migration touches only `role`
  columns; code edits target only role enum refs + the listed literal `"admin"` role
  comparisons; app name / URL prefix / Django admin / frontend route untouched.
- **Evidence gate change touches existing roles** — mitigated by tests covering
  superadmin, space_manager, guest_admin, inventory_manager (incl. promotion) and
  suspended-user denial.
- **Migration reverse** — makerspaces reverse is *lossy* (inventory_manager→guest_admin)
  and documented as such; accounts reverse is exact.
- `max_length=32` accommodates `space_manager` (13) and `inventory_manager` (17).
- Internal API path rename (`users/admins`→`users/space-managers`) is safe: no external
  consumers (pre-release); frontend updated in lockstep.

## Out of scope
- Replacing `prompt()`-based staff UI actions; finer role-based frontend nav.
- Refactoring/securing direct-loan & self-checkout (separate, already-flagged cleanup).
