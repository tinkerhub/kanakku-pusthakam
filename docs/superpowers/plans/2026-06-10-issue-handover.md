# Plan — Issue / Handover Flow (accepted → issued)

**Phase:** Issue / Handover (PRD §6.3, §10.1, §11, §14, §17)
**Scope decision:** This phase covers the handover/issue half of the
issue+return cycle only (`accepted → issued`). Return (`issued →
returned|partially_returned|closed_with_issue`) is the next phase. Tool/asset QR
(`InventoryAsset`) and the generic polymorphic `QrCode` table are deferred to the
later individual-tracking phase — boxes carry their QR payload directly today.

## Goal

Let an admin / guest admin / superadmin take an `accepted` request through a
traceable physical handover: assign (scan) a box QR, attach a mandatory issue
photo, and mark the request `issued` — with availability math moving stock
`reserved → issued`, an immutable box-scan record, and full audit trail. Enforce
the load-bearing hard rule: **hardware cannot be issued without both a box QR
scan and an issue photo.**

## Open questions resolved (PRD §18)

- **Box QR representation:** Reuse the existing `Box.code` opaque payload as the
  box QR. Do *not* introduce the generic `QrCode` table yet — only boxes exist,
  so a polymorphic table would be speculative. Revisit when tool/asset QR lands.
- **One box per request:** MVP = one assigned box per request (PRD §18 left this
  open; single-box is the simpler, listed-MVP behavior).
- **Partial issue / changing accepted quantities at handover:** Out of scope for
  this phase. Issue the **full accepted quantity** (`issued_quantity =
  accepted_quantity`). The "issued may not exceed accepted without permission"
  rule is satisfied trivially (we never exceed accepted). Partial issue + the
  permissioned override are deferred.
- **Evidence ↔ request link direction:** The request points at the evidence
  (FK on `HardwareRequest`), honoring the Phase 3 immutability rule that
  `EvidencePhoto` rows are never mutated after creation. The issue *remark*
  lives on the request, not on the immutable evidence row.

## Data model changes

### `apps/boxes/models.py` — new `BoxScan` (immutable, append-only)

```
BoxScan
- makerspace   FK Makerspace (PROTECT)
- box          FK Box (PROTECT)
- request      FK HardwareRequest (SET_NULL, null=True)   # nullable for future non-request scans
- actor        FK User (PROTECT)
- context      char: "issue" | "return"                   # only "issue" used this phase
- created_at   auto_now_add
```
- **(rev — review finding 3)** Immutability is enforced at BOTH layers, matching
  the existing `EvidencePhoto`/`AuditLog` pattern, not Python alone:
  - Model guard: `save()` raises if `pk` is not None; `delete()` always raises
    (mirrors `apps/evidence/models.py:26-32`).
  - **DB trigger migration** rejecting `UPDATE`/`DELETE` on the `boxes_boxscan`
    table — copy the `RunSQL` trigger pattern from
    `apps/evidence/migrations/0002_evidencephoto_immutable_triggers.py`. The
    trigger is the real guard; the model guard is defense-in-depth.
  This is the PRD §11 immutable "Box QR scan" evidence record and §10.1 history.

### `apps/hardware_requests/models.py` — `HardwareRequest` new fields

```
- assigned_box    FK boxes.Box (SET_NULL, null=True, related_name="+")
- issued_by       FK User (SET_NULL, null=True, related_name="+")
- issued_at       DateTimeField(null=True)
- issue_evidence  OneToOneField(evidence.EvidencePhoto, PROTECT, null=True,
                                 related_name="issued_request")
- issue_remark    TextField(blank=True)
```
- `issue_evidence` is **OneToOne** so the DB itself guarantees one evidence photo
  is never attached to two requests (kills the double-attach race without a
  service-level check).

**(rev — review finding 2) Race-safe "one active loan per box" constraint** on
`HardwareRequest`:
```
UniqueConstraint(
    fields=["assigned_box"],
    condition=Q(status__in=["issued", "partially_returned"]),
    name="uniq_active_loan_per_box",
)
```
A Postgres partial unique index: at most one row may hold a given `assigned_box`
while in an out-on-loan status. Nullable `assigned_box` rows and non-out statuses
are unconstrained, so multiple `accepted` requests may *pre-assign* the same box,
but only the **first to issue wins** — the second `issue` hits `IntegrityError`,
caught and re-raised as `BoxValidationError` ("Box is already out on another
loan."). This is the DB-level race guard; the assign-time check below is just
friendlier early UX, not the real guarantee.

`HardwareRequestItem` needs no new fields (`issued_quantity` already exists).

### Migrations

- `hardware_requests`: add the five fields **and** the `uniq_active_loan_per_box`
  partial unique constraint (depends on `boxes` + `evidence`).
- `boxes`: (a) create `BoxScan`; (b) a follow-up `RunSQL` migration adding the
  UPDATE/DELETE-rejecting trigger on `boxes_boxscan` (mirror evidence `0002`).

## Service layer

### `apps/inventory/availability.py` — add `issue_items(request)`

- Must run inside `transaction.atomic()` (same guard as `reserve_for_request`).
- Row-lock the products (`select_for_update`, ordered by pk — same lock order as
  `reserve_for_request` to avoid deadlocks).
- For each item with `accepted_quantity > 0`: assert
  `product.reserved_quantity >= accepted_quantity` (raise `InsufficientStock`
  otherwise — never go below zero), then
  `reserved_quantity -= accepted_quantity`, `issued_quantity += accepted_quantity`.
- The `qty_sum_within_total` check constraint is unaffected (we move between
  buckets, total unchanged) — but compute carefully so the model save never
  violates a non-negativity constraint.
- Set `item.issued_quantity = item.accepted_quantity` and save the item.
- This is the **only** place reserved/issued counts move at issue time.

### `apps/hardware_requests/workflow.py` — add `assign_box`, `issue_request`

New exception: `BoxValidationError` (maps to 400). Reuse `InvalidTransition`
(409) and `RequestValidationError` (400).

**`assign_box(actor, request, box_code)`** — resolving the box by its scanned
code *is* the scan:
- `transaction.atomic()` + `_locked_request`.
- Require `locked.status == ACCEPTED` (else `InvalidTransition` → 409).
- Resolve `Box` by `code` **within `locked.makerspace`** and `is_active=True`;
  not found → `BoxValidationError` ("Unknown or inactive box.").
- Best-effort early UX check: reject if the box is currently the `assigned_box`
  of another request in `issued`/`partially_returned` — `BoxValidationError`.
  (Not the real guard; the `uniq_active_loan_per_box` constraint at issue time
  is — see finding 2 above.)
- Set `locked.assigned_box = box`, save.
- Create immutable `BoxScan(context="issue", box, request=locked, actor,
  makerspace)`.
- `audit.record(actor, "box.assigned", ...)` and `audit.record(actor,
  "box.scanned", ...)`.
- Return `locked`.

**`issue_request(actor, request, evidence_id, remark="")`** — `request` is
already the tenant-scoped object the view resolved (404-before-403), so
`request.makerspace_id` is the authoritative tenant:
- **(rev — review finding 4) Scoped evidence validation BEFORE any storage I/O:**
  fetch `evidence = EvidencePhoto.objects.filter(pk=evidence_id,
  makerspace_id=request.makerspace_id, evidence_type="issue").first()`. If
  `None` → `RequestValidationError` ("Invalid issue evidence."). This rejects
  missing / cross-tenant / wrong-type evidence with NO storage HEAD and NO
  cross-tenant existence leak.
- **Fail-closed storage check, outside the transaction (now that scope is
  confirmed):** `storage.object_exists(evidence.object_key)` — if `False` raise
  `EvidenceNotUploaded` (→ 409 `evidence_not_uploaded`); `StorageUnavailable`
  propagates (→ 503). Verify-then-act: the upload happened via the Phase 3
  presigned POST; we confirm bytes landed before issuing.
- `transaction.atomic()` + `_locked_request`:
  - Require `status == ACCEPTED` (else `InvalidTransition` → 409).
  - **(rev — review finding 1) Box-scan hard rule, fail-closed on the immutable
    scan record (not the mutable FK):** require
    `BoxScan.objects.filter(request=locked, box_id=locked.assigned_box_id,
    context="issue").exists()` AND `locked.assigned_box_id` set, else
    `RequestValidationError` ("Box scan required before issue."). Presence of an
    immutable `BoxScan` is the proof a scan occurred — a stray write to
    `assigned_box` alone can never satisfy issue.
  - `availability.issue_items(locked)`.
  - Set `issue_evidence=evidence` (OneToOne guards double-use),
    `issue_remark=remark`, `issued_by=actor`, `issued_at=now`, `status=ISSUED`;
    save. Wrap the save: `IntegrityError` from the `issue_evidence` OneToOne →
    `RequestValidationError` ("Evidence already used."); `IntegrityError` from
    `uniq_active_loan_per_box` → `BoxValidationError` ("Box is already out on
    another loan."). Distinguish by constraint name in the error, else fall back
    to a generic conflict.
  - `audit.record(actor, "evidence.attached", target=evidence, ...)` and
    `audit.record(actor, "request.issued", target=locked, ...)`.
  - `transaction.on_commit(notify_request_issued)`.
- Return `locked`.

### `apps/hardware_requests/notifications.py`

- Add `notify_request_issued(request)` Telegram seam (same fail-safe shape as the
  existing `notify_request_submitted`).

## API layer

### `apps/hardware_requests/permissions.py`

- `CanAssignBox` — active + `makerspaces_for_action(user, ASSIGN_BOX)` non-empty.
- `CanIssueRequest` — active + `makerspaces_for_action(user, ISSUE_REQUEST)`.
  (Both mirror the existing `CanViewHandoverQueue` active-status pattern so
  restricted/suspended staff are blocked.)

### `apps/hardware_requests/views.py` + `urls.py`

All admin actions follow the established **404-before-403** pattern:
`scope_by_makerspace(user, qs)` → `get_object_or_404` → `rbac.can(user, action,
makerspace_id)` else `PermissionDenied`.

- `POST /admin/requests/:pk/assign-box` — body `{box_code}` (AssignBoxSerializer);
  perm `CanAssignBox`, action `ASSIGN_BOX`. Returns `AdminRequestSerializer`.
- `POST /admin/requests/:pk/issue` — body `{evidence_id, remark?}`
  (IssueRequestSerializer); perm `CanIssueRequest`, action `ISSUE_REQUEST`.
  Returns `AdminRequestSerializer`.
- `GET /admin/makerspace/:id/active-loans` — `issued` (+ later
  `partially_returned`) requests for the makerspace; perm `CanViewHandoverQueue`
  (issue authority), action `ISSUE_REQUEST`. Listed in PRD §14; cheap to add now
  since issue produces active loans.

### `apps/hardware_requests/serializers.py`

- `AssignBoxSerializer { box_code: CharField }`.
- `IssueRequestSerializer { evidence_id: IntegerField, remark: CharField(blank,
  optional) }`.
- Extend `AdminRequestSerializer` with read-only `assigned_box_label`
  (`source="assigned_box.label"`, nullable), `issued_at`, and per-item
  `issued_quantity` on `AdminRequestItemSerializer`.

### `apps/hardware_requests/exceptions.py`

- Map new exceptions: `BoxValidationError` → 400 `box_validation_error` (bad/
  unknown box code); **`BoxUnavailable` → 409 `box_unavailable`** (box already
  out on another loan — a state conflict, like `InvalidTransition`, used by both
  the assign-time occupancy check and the issue-time `uniq_active_loan_per_box`
  IntegrityError); `EvidenceNotUploaded` → 409 `evidence_not_uploaded`;
  `StorageUnavailable` → 503 `evidence_storage_unavailable`.

### Swagger

- `@extend_schema` on both new actions + active-loans, reusing the existing
  `ACTION_ERROR_RESPONSES` / `ADMIN_LIST_ERROR_RESPONSES` maps (add 503 to the
  issue action's responses).

## Audit events emitted (PRD §11)

`box.assigned`, `box.scanned`, `evidence.attached`, `request.issued`.

## Tests (`backend/tests/test_issue.py`) — external behavior (PRD §17)

- assign-box on an `accepted` request: sets `assigned_box`, creates one
  immutable `BoxScan(context=issue)`, emits `box.assigned`/`box.scanned`.
- assign-box rejects a box from another makerspace (BoxValidationError) and a
  non-`accepted` request (409).
- assign-box rejects a box currently out on another issued request.
- issue with NO `BoxScan` for the request → 400, even if `assigned_box` is
  force-set directly (fail-closed on the scan record, finding 1).
- issue without uploaded evidence (object missing in storage) → 409
  (`object_exists` mocked False); `StorageUnavailable` mocked → 503.
- cross-tenant / wrong-type `evidence_id` → 400 with **no** `object_exists` call
  (assert the storage mock was not invoked — finding 4).
- issue happy path: `accepted → issued`, `issued_by/issued_at/issue_evidence`
  set, availability moves `reserved → issued`, item `issued_quantity ==
  accepted_quantity`, audit `request.issued` + `evidence.attached` present.
- guest admin **can** issue an accepted request; cannot when suspended.
- cross-makerspace admin gets 404 (scoping) before 403.
- double-issue same request → 409; reusing an evidence row on a second request
  → 400 ("Evidence already used", OneToOne).
- **two requests pre-assigned the same box; first issue succeeds, second → 409**
  `BoxValidationError` via `uniq_active_loan_per_box` (finding 2).
- `BoxScan` is immutable: updating/deleting an existing row raises (model guard
  and, where the test DB supports it, the DB trigger — finding 3).
- `availability.issue_items` raises `InsufficientStock` rather than driving any
  bucket below zero (defensive).
- Storage interactions (`object_exists`) are mocked — no live MinIO in tests.

## CLAUDE.md

- Update Project Status + source map: note the Issue/Handover flow, `BoxScan`,
  `availability.issue_items`, and the new endpoints. Note Return is still pending.

## Risks / notes

- `object_exists` is an external call; it runs **before** the transaction (not
  under the row lock) and fails closed. Acceptable.
- Reusing `Box.code` as the QR means revoke/regenerate = `is_active`/new box for
  now; the richer `QrCode` lifecycle arrives with tool/asset tracking.
- No partial issue keeps the math trivial and avoids leftover-reservation
  release logic in this phase.

## Revision log

- **Round 1 (Codex Stage 1):** NEEDS_REVISION → 4 findings, all applied:
  1. Box-scan rule made fail-closed on the immutable `BoxScan` row, not the
     mutable `assigned_box` FK.
  2. Race-safe `uniq_active_loan_per_box` partial unique constraint prevents one
     box being out on two loans; second issue → `BoxValidationError`.
  3. `BoxScan` gets a DB UPDATE/DELETE-reject trigger (not just a Python guard),
     matching `EvidencePhoto`/`AuditLog`.
  4. Evidence makerspace/type validated (scoped to the request's makerspace)
     BEFORE any storage HEAD — no cross-tenant storage I/O or existence leak.
  Approved-as-is by Codex: availability math + lock ordering, `accepted→issued`
  guard, photo requirement, 404-before-403 scoping.
- **During implementation (Claude verify):** two corrections applied directly:
  (a) `_locked_request` must NOT `select_related` the nullable `assigned_box` —
  Postgres rejects `SELECT … FOR UPDATE` across the nullable side of an outer
  join (it broke accept/reject too); issue only needs `assigned_box_id`.
  (b) split box errors: `BoxValidationError`→400 (bad code) vs
  `BoxUnavailable`→409 (box already out), since a box-occupancy conflict is a
  state conflict, not malformed input.
```
