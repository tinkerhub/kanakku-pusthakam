# Plan — Request Workflow: Submission + Accept/Reject

**Date:** 2026-06-10
**Phase scope (user-approved):** Public request submission + admin accept/reject only.
Issue / assign-box / return are a later phase (they depend on QR scans + evidence attach).

## Locked decisions (PRD §18)

1. **Reserve timing:** inventory moves `available → reserved` **at acceptance**, not at
   submission. Submission only records intent. (§18 Q3)
2. **Check-in API:** build a fail-closed `checkin` client with a fixed internal contract
   `verify(makerspace, identifier) -> {username, external_id}`. A configurable **stub**
   backend runs until the real endpoint is wired; HTTP backend isolates the external API.
   If the API is down/unreachable, submission is rejected with a safe 503 — never crashes. (§18 Q1/Q2)
3. **Requester identity:** requesters are `User` rows (`role=requester`). Check-in result is
   mapped to a get-or-create requester keyed on `external_checkin_user_id`. Submission is
   blocked (403) when `access_status != active`. (§6.5, §17)
   - **Race safety (Codex #1):** `external_checkin_user_id` is currently a plain non-unique
     `CharField`, so concurrent first-time submissions could create duplicate requester rows.
     Add a **partial unique constraint** on `User.external_checkin_user_id` where it is
     non-empty (`UniqueConstraint(fields=["external_checkin_user_id"], condition=~Q(...=""),
     name="uniq_external_checkin_user_id")`) — staff rows keep blank ids and are unaffected.
     `submit_request` uses `get_or_create` and **retries once on `IntegrityError`** (re-fetch),
     so a lost race resolves to the existing row. Uniqueness is **global** (the `User` model has
     no makerspace owner — a checked-in identity is one person across makerspaces).
   - **`User.username` collision safety (Codex round 2):** `User` inherits Django's **unique**
     `username`. The check-in display name must **not** be written to `User.username` (it could
     collide with a staff account or another requester). Instead, requester rows are created with
     a **collision-proof internal username derived from the unique external id**:
     `username = "checkin_" + sha256(external_id).hexdigest()`. A **hex hash** is used (not
     the raw id) because the external id may contain characters Django's inherited
     `UnicodeUsernameValidator` rejects (it allows only alphanumerics and `@ . + - _`, so a literal
     `:` or arbitrary punctuation would yield an invalid `User` for admin/forms). The `checkin_` +
     hex form is always validator-clean and collision-proof (1:1 with the external id, since the
     username is a function of the unique external id).
     `get_or_create(external_checkin_user_id=external_id, defaults={username, role=requester,
     access_status=active})` keys on the external id only. The human-readable check-in name lives
     solely in the snapshot field `HardwareRequest.requester_username`, never in `User.username`.
4. **Telegram:** out of scope here (separate phase). The workflow calls a thin
   `notifications.notify_request_submitted(request)` **seam** (structured-log no-op now) so the
   Telegram phase plugs in without touching workflow code — honoring the architecture rule
   "Telegram calls the workflow, the workflow triggers alerts via a hook."

## State machine (this phase)

```
(public submit) -> pending_approval
pending_approval -> accepted   (admin/superadmin; reserves inventory)
pending_approval -> rejected   (admin/superadmin; reason required)
```

`issued / partially_returned / returned / closed_with_issue` are defined on the model enum
for forward-compat but have **no transitions wired** this phase.

## Architecture invariants honored

- **Request Workflow Module is the single source of truth for state transitions.** All status
  changes go through `apps/hardware_requests/workflow.py`; views never mutate `status` directly.
  Mirrors the proven `apps/printing/workflow.py` (atomic + `select_for_update` + audit +
  `transaction.on_commit` hooks).
- **Inventory Availability Module owns all quantity math.** New `apps/inventory/availability.py`
  is the only place `available/reserved` counts change. Invariant "availability never goes
  below zero" enforced there (guard + existing DB `CheckConstraint`s).

## New Django app: `apps/hardware_requests`

**Renamed from `apps/requests` (Codex #2).** Naming an app `requests` while the check-in HTTP
backend pulls in the third-party `requests` library is avoidable risk, so the workflow app is
`apps/hardware_requests` (label `hardware_requests`). The check-in HTTP client lives in the
separate `apps/checkin` app and may safely `import requests`.

### `models.py`

`HardwareRequest`:
- `makerspace` FK → Makerspace (CASCADE)
- `requester` FK → User (PROTECT, `related_name="hardware_requests"`)
- `requester_username` CharField (denormalized snapshot from check-in)
- `status` CharField(choices=Status) default `pending_approval`
- `Status` TextChoices: `draft, pending_approval, rejected, accepted, issued,`
  `partially_returned, returned, closed_with_issue`
- `requested_for` TextField(blank=True) — optional purpose note (§13)
- `rejection_reason` TextField(blank=True)
- `accepted_by` FK→User null (SET_NULL, `+`); `accepted_at` DateTime null
- `closed_by` / `closed_at` — defined null for forward-compat (not set this phase)
- `public_token` UUIDField(default=uuid4, unique, editable=False) — used by the public
  status endpoint instead of the sequential PK (prevents enumeration of other requests)
- `created_at` / `updated_at`
- index on (`makerspace`, `status`)

`HardwareRequestItem`:
- `request` FK → HardwareRequest (CASCADE, `related_name="items"`)
- `product` FK → InventoryProduct (PROTECT)
- `requested_quantity` PositiveInteger
- `accepted_quantity` / `issued_quantity` / `returned_quantity` / `damaged_quantity` /
  `missing_quantity` — PositiveInteger default 0 (only `accepted_quantity` set this phase)
- CheckConstraint `requested_quantity >= 1`

### `workflow.py` — single source of truth

- `submit_request(makerspace, identifier, items, requested_for="")`:
  1. `checkin.verify(makerspace, identifier)` (fail-closed → `CheckinUnavailable`).
  2. get-or-create requester `User` by `external_checkin_user_id` (internal `username` =
     `"checkin_" + sha256(external_id).hexdigest()`, validator-clean + collision-proof); snapshot the
     check-in display name into `request.requester_username`.
  3. assert `access_status == active` else `RequesterBlocked`.
  4. validate items: non-empty; each product in `makerspace`, `is_public`, not archived;
     `quantity >= 1`; **no duplicate `product_id` in one submission (Codex #3)** — duplicate
     lines are rejected at the serializer boundary (`RequestValidationError`), so per-product
     stock is never checked/decremented twice.
  5. atomically create `HardwareRequest(status=pending_approval)` + items.
  6. `audit.record(requester, "request.submitted", makerspace=…, target=request)`.
  7. `transaction.on_commit(lambda: notifications.notify_request_submitted(request))`.
  - returns the request.
- `accept_request(actor, request)`:
  - atomic; `select_for_update` the request; assert status `pending_approval` else
    `InvalidTransition`.
  - set each item `accepted_quantity = requested_quantity` (admin qty edits = §18 Q9, deferred).
  - `availability.reserve_for_request(request)` (raises `InsufficientStock` → 409, rolls back).
  - status→`accepted`, `accepted_by`/`accepted_at`; save update_fields.
  - `audit.record(actor, "request.accepted", …)`.
- `reject_request(actor, request, reason)`:
  - atomic; assert status `pending_approval`; require non-empty reason.
  - status→`rejected`, `rejection_reason`. No inventory change (nothing reserved yet).
  - `audit.record(actor, "request.rejected", …, meta={"reason": reason})`.
- Exceptions: `InvalidTransition`, `InsufficientStock` (from availability), `RequesterBlocked`,
  `CheckinUnavailable`, `CheckinDenied`, `RequestValidationError`.

### `permissions.py`

`CanReviewRequest` (DRF permission), action-aware like `printing/permissions.py`:
`has_permission` returns 403 for actors lacking `ACCEPT_REQUEST`/`REJECT_REQUEST` in **any**
makerspace (a pure requester or guest-admin-only user is denied before object lookup).

**Object-action scoping order (Codex #5) — precise, to avoid cross-tenant existence leaks:**
the accept/reject views resolve the request through a **membership-scoped** queryset
(`rbac.scope_by_makerspace(actor, HardwareRequest.objects…)`) so a request in a makerspace the
actor has **no membership in** returns **404** (existence not leaked). Only after the object is
found do we call `rbac.can(actor, ACCEPT_REQUEST|REJECT_REQUEST, obj.makerspace_id)`, returning
**403** when the actor is a member of that makerspace but lacks the specific action (e.g. a guest
admin attempting accept). Never `get(pk=…)` unscoped before the permission check.

### `serializers.py`

- `RequestSubmitSerializer` — `identifier`, `requested_for`, `items: [{product_id, quantity}]`.
- `RequestStatusSerializer` — public, **strict allowlist (Codex #6)**: `status`,
  `rejection_reason`, `created_at`, and per item only
  `product_name` (string) + `requested_quantity`. **Never** exposes: `requester_username`
  (PII — check-in identity; Stage-4 review fix), product id, box fields,
  `Box.code`, `storage_location`, requester user id/email/phone, `public_token` of other
  requests, accepted/issued/returned quantities, audit metadata, or any evidence field. Tests
  assert the **absence** of each of these keys, not just "no obvious leak".
- `AdminRequestSerializer` — fuller view for staff queues (requester, items, timestamps).

### `views.py`

Public (AllowAny, **scoped throttles — Codex #8**):
- `POST /api/public/<slug>/checkin/verify` → `{identifier}` → `{username}` (UI convenience;
  calls the same `checkin.verify`). `ScopedRateThrottle` scope `checkin_verify`.
- `POST /api/public/<slug>/requests` → submit; returns `{public_token, status}`.
  `ScopedRateThrottle` scope `request_submit`.
- `GET  /api/public/requests/<public_token>/status` → `RequestStatusSerializer`.
  `ScopedRateThrottle` scope `request_status`.

Admin (IsAuthenticated + `CanReviewRequest`, makerspace-scoped):
- `GET  /api/admin/makerspace/<id>/pending-requests` — `scope_by_action(actor, ACCEPT_REQUEST,…)`,
  filtered status=pending_approval.
- `GET  /api/admin/makerspace/<id>/accepted-requests` — handover queue, scoped by
  `ISSUE_REQUEST` (so guest admins also see it), status=accepted.
- `POST /api/admin/requests/<id>/accept` — membership-scoped fetch (404) then
  `can(actor, ACCEPT_REQUEST, obj.makerspace_id)` (403); 409 on insufficient stock / invalid transition.
- `POST /api/admin/requests/<id>/reject` — membership-scoped fetch (404) then
  `can(actor, REJECT_REQUEST, obj.makerspace_id)` (403); reason required (400 if blank).

**OpenAPI (Codex #8):** every endpoint uses `@extend_schema` with explicit typed error responses
for the codes it can return — 400 (validation), 403 (`RequesterBlocked`/`CheckinDenied`/wrong
action), 404 (cross-tenant / unknown token), 409 (`InvalidTransition`/`InsufficientStock`),
503 (`CheckinUnavailable`). A shared `ErrorSerializer` (`{detail, code}`) gives a consistent
typed body. A small DRF exception handler maps the workflow exceptions to these status codes.

### `admin.py`

Tenant-scoped `HardwareRequestAdmin` using `rbac.scope_by_action` (mirrors printing admin fix);
read-mostly (status changes must go through the workflow, so admin save is restricted).

### `notifications.py`

`notify_request_submitted(request)` — structured-log seam (documented Telegram integration point).

## New Django app: `apps/checkin`

- `client.py`:
  - `verify(makerspace, identifier) -> CheckinResult(username, external_id)`.
  - Backend selected by `settings.CHECKIN_MODE`: `"stub"` (echoes identifier as username/external_id;
    default for dev/tests) or `"http"` (POSTs to `CHECKIN_API_URL` with timeout; maps response).
  - **Two failure modes (Codex #7), distinct status codes:**
    - `CheckinUnavailable` → **503**: cannot determine — network error, timeout, non-2xx,
      malformed response. Fail-closed; never lets the request proceed.
    - `CheckinDenied` → **403**: service healthy and explicitly says the identifier is invalid /
      not checked in (only distinguishable in `http` mode; stub never denies).
  - Never raises an unhandled exception into the request flow. Structured logging on failure.
  - **Config validation (Codex #7):** when `CHECKIN_MODE == "http"`, `apps.py.ready()` (or an
    explicit `check`) asserts `CHECKIN_API_URL` + `CHECKIN_TIMEOUT` are set and `requests` is
    importable, else `ImproperlyConfigured` — misconfiguration fails fast at boot, not per request.
- No models. `apps.py` (with the http-mode config check) only. Adds `requests` to
  `backend/requirements.txt` (currently absent — Codex #2).

## Inventory Availability: `apps/inventory/availability.py` (NEW)

Quantity-math module (the Inventory Availability Module seam beyond `public_availability.py`):
- `class InsufficientStock(Exception)`.
- `reserve_for_request(request)`: inside the caller's atomic block, lock each item's product
  with `select_for_update()` ordered by `product_id` (deadlock-safe), assert
  `available_quantity >= accepted_quantity`, then `available -= q; reserved += q`;
  `save(update_fields=[…])`. Raises `InsufficientStock` (rolls back the whole accept).
  Because duplicate product lines are rejected at the boundary (Codex #3), each product is
  locked and decremented exactly once per accept.
- `release_reservation(request)` implemented now **only if needed** — with reserve-at-acceptance,
  reject happens from `pending_approval` (nothing reserved), so it is **not** wired this phase
  (avoid speculative code); added when the issue/return phase needs it.

**Correction on existing constraints (Codex #4):** `inventory/models.py` today only enforces
**per-bucket non-negativity** (`available >= 0`, etc.) — there is **no** existing constraint that
`available + reserved + issued + damaged + lost <= total_quantity`. So the per-bucket constraints
do **not** by themselves protect the inventory invariant; the availability service is what keeps
the buckets consistent. To harden this at the DB level, this phase **adds a `CheckConstraint`**
`available + reserved + issued + damaged + lost <= total_quantity` (new inventory migration).
Implementation must confirm `seed_demo` data already satisfies it (adjust the seed if not) so the
migration applies cleanly.

## Config changes

- `config/settings.py`: add `apps.hardware_requests`, `apps.checkin` to `INSTALLED_APPS`; add
  `CHECKIN_MODE` (default `stub`), `CHECKIN_API_URL`, `CHECKIN_TIMEOUT` via `env`. Add
  `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` for scopes `checkin_verify`, `request_submit`,
  `request_status` (env-overridable defaults, e.g. `30/min`, `10/min`, `60/min`), and ensure
  `ScopedRateThrottle` is available. Register the workflow exception handler
  (`EXCEPTION_HANDLER`) that maps workflow exceptions → 400/403/404/409/503 typed bodies.
- `config/urls.py`: mount the public routes (`api/v1/public/…`, matching the existing
  `api/v1/` mount style) and admin request routes.
- `backend/.env.example`: document `CHECKIN_MODE` / `CHECKIN_API_URL` / `CHECKIN_TIMEOUT` and
  the throttle-rate overrides.
- `backend/requirements.txt`: add `requests` (used by the check-in http backend; currently absent).

## Migrations (explicit — Codex #8)

- `accounts/0002_*`: partial `UniqueConstraint` on `User.external_checkin_user_id`
  (`condition=~Q(external_checkin_user_id="")`).
- `inventory/0004_*`: `CheckConstraint` `available+reserved+issued+damaged+lost <= total_quantity`.
- `hardware_requests/0001_initial`: `HardwareRequest` + `HardwareRequestItem`.
- `checkin`: no models → no migration.
- All migrations applied and verified before tests; confirm existing seed/test data satisfies the
  new inventory constraint.

## Audit actions emitted

`request.submitted`, `request.accepted`, `request.rejected` (all via `apps.audit.services.record`).
The accept audit is written **inside** the same transaction as the reservation, so an
`InsufficientStock` rollback also rolls back any `request.accepted` entry (verified by test).

## Tests (Stage 3) — external behavior (PRD §17)

- Restricted/suspended requester cannot submit (403).
- Submission creates pending request + items; emits `request.submitted` audit + notify seam called.
- Check-in **unavailable** → submission 503, **no** request row created (fail-closed).
- Check-in **denies** identifier (http mode) → 403, no request row.
- Duplicate product lines in one submission → 400 (Codex #3).
- Public status endpoint by token returns the strict allowlist only; test asserts **absence** of
  product id, box fields, `Box.code`, storage_location, requester id/email/phone, accepted/issued
  quantities, audit, evidence (Codex #6); unknown token → 404.
- Admin accept reserves inventory (`available↓`, `reserved↑`) and writes `request.accepted`.
- Accept with insufficient stock → 409, **no** partial reservation, status stays pending, and
  **no `request.accepted` audit row** was written (rollback test — Codex #8).
- Admin can accept only requests in assigned makerspace: request in a makerspace the actor has no
  membership in → **404**; a guest-admin member attempting accept in their own makerspace → **403**
  (Codex #5).
- Guest admin cannot accept/reject (403); guest admin DOES see accepted-requests queue.
- Reject requires reason (blank → 400); sets status + rejection_reason; no inventory change.
- Availability never goes below zero (concurrent-accept guard: two accepts contending for the last
  unit — one succeeds, the other 409s).
- Throttle: exceeding `request_submit`/`checkin_verify` rate → 429.

## Risks / trade-offs

- **Reserve-at-acceptance** means pending requests don't hold stock — two requests can both be
  accepted only up to available; the second hits `InsufficientStock` 409 (correct, surfaced).
- **Stub check-in** is intentionally permissive (echoes identifier, never denies). Real
  verification + the deny path are gated behind `CHECKIN_MODE=http`; the boundary contract
  (`verify → {username, external_id}`, `CheckinUnavailable`/`CheckinDenied`) won't change when swapped.
- **Global requester uniqueness** on `external_checkin_user_id`: one checked-in identity = one
  `User` across all makerspaces. Acceptable because the check-in service is the global identity
  source; revisit only if a per-makerspace identity model ever emerges.
- **New inventory sum constraint** could reject inconsistent legacy/seed rows; implementation
  verifies and (if needed) fixes seed data so the migration applies cleanly.
- **No release_reservation wired** is deliberate (reject is pre-reservation); revisit in issue/return.

## Revision log

- **Codex round 1 → NEEDS_REVISION (8 findings), all addressed:** app renamed
  `requests`→`hardware_requests` (#2, +`requests` dep); requester race fixed via partial unique
  constraint + get_or_create retry (#1); duplicate product lines rejected at boundary (#3);
  corrected inventory-constraint claim + added sum `CheckConstraint` (#4); precise
  membership-scoped-fetch-then-`can()` 404/403 order (#5); strict status allowlist with
  absence-asserting tests (#6); `CheckinUnavailable`(503)/`CheckinDenied`(403) split + http-mode
  config validation (#7); explicit migrations, scoped throttles, typed OpenAPI error schemas, and
  audit-rollback tests (#8).
- **Codex round 2 → NEEDS_REVISION (1 new finding), addressed:** requester `User.username`
  collision avoided by deriving an internal username from the unique external id; the
  human-readable check-in name is kept only in `HardwareRequest.requester_username`.
- **Codex round 3 → NEEDS_REVISION (1 finding), addressed:** the internal username format is now
  `"checkin_" + sha256(external_id).hexdigest()` (hex hash) so it satisfies Django's
  `UnicodeUsernameValidator` even when the external id contains characters like `:` — the earlier
  `checkin:{external_id}` form would have produced validator-invalid `User` rows.
