# Project Handover — TinkerSpace Inventory Manager

**Date:** 2026-06-11
**Audience:** Codex (and any engineer picking up the build)
**Purpose:** A single source of truth for *what is built*, *what is in flight*, and *what is left*, so work can continue without re-discovering the codebase.

Read this alongside:
- `docs/prd-architecture.md` — the PRD (sections referenced as §N below).
- `docs/roadmap.md` — the dependency-ordered phase plan (Phases 1–11).
- `CLAUDE.md` (repo root) — engineering conventions, hard rules, current source map.
- `~/.claude/CLAUDE.md` — the gated Stage 1–6 workflow that governs every change.

---

## 1. TL;DR — where the project stands

The **backend core lending pipeline is ~85% built**: a public user can browse inventory, verify, and submit a request; staff can accept/reject, assign a box, and issue with evidence; and the **return flow is freshly implemented but not yet committed** (see §3). What remains is mostly **the QR/asset module, the entire staff/admin frontend, Telegram, access-restriction endpoints, admin CRUD REST surface, and API hardening**.

| Layer | State |
|---|---|
| Backend domain pipeline (submit → accept → issue → **return**) | Built; return uncommitted, tests passing |
| Backend QR module (QrCode model, tool/asset QR, generate/print/revoke) | **Not started** (only `Box` + `BoxScan` exist) |
| Backend admin REST CRUD (inventory, makerspaces, users) | **Not started** (Django admin only) |
| Access restriction (restrict/restore) endpoints | **Not started** (accountability rows are written; superadmin action API missing) |
| Telegram integration | **Seam only** (`notifications.py` stubs, no bot) |
| Check-In API | **Stub backend only** (real HTTP integration deferred, shape unresolved) |
| Frontend | **Public inventory page only**; no admin/guest-admin/handover/return UI |
| API hardening (Phase 10) | **Partial** — `/api/v1/` prefix is mounted; public-auth (publishable keys), rate limits, CORS allowlist, and typed client are **not done** (HMAC-in-browser still in use) |

---

## 2. What is DONE (committed)

Verified against git history and the current source tree.

### Phase 1 — Admin theme + public frontend (commit history pre-Phase 2)
- Django admin themed with **django-unfold** (forced dark + violet). Site name via `ADMIN_SITE_NAME`.
- Frontend dev server on port 5000; CORS updated.

### Phase 2 — Auth + RBAC + multi-tenant scoping (`2981d9b`)
- Custom `User` model (`AUTH_USER_MODEL`) with `role` and `access_status`.
- `MakerspaceMembership` (user ↔ makerspace ↔ role) scopes admins/guest-admins; superadmin sees all.
- `apps/accounts/rbac.py` — the Auth & RBAC module: `can(...)`, action-scoped `makerspaces_for_action` / `scope_by_action`.
- JWT auth views: `login`, `logout`, `me`. Refresh blocks suspended/restricted/inactive users.
- API-client **HMAC registry** (`apps/apiclients/`) for the public surface (note: this is the thing Phase 10 must replace for third-party use).
- Tests: `test_auth.py`, `test_rbac.py`, `test_memberships.py`.

### Phase 3 — Object storage + evidence + audit (`a8613bc`)
- `apps/audit/` — append-only `AuditLog` + `audit.record(...)`. Append-only enforced in model methods **and** Postgres triggers. `target_id` is a **string, not an FK** (survives loan deletion — this is the permanent ledger; see retention model in §3).
- `apps/evidence/` — immutable `EvidencePhoto` rows, S3/MinIO storage, presigned **POST** upload URLs (exact MIME binding + content-length range) and short-lived signed GET URLs.
- Tests: `test_audit.py`, `test_evidence.py`.

### 3D Printing Manager (`cd102c5`) — *adjacent feature, not a numbered phase*
- `apps/printing/` — `PrintBucket`/`PrintRequest`, row-locked audited `workflow.py`, `CanManagePrinting` permission, fail-safe branded SMTP `emails.py`. Templates in `backend/templates/email/`.
- Tests: `test_printing.py`.

### Phase 4 — Request workflow: submit → accept/reject (`6f52c07`)
- `apps/hardware_requests/` — `HardwareRequest` / `HardwareRequestItem` models.
- `workflow.py` is the **single source of truth** for status transitions: `submit_request` / `accept_request` / `reject_request`, atomic + row-locked + audited. **Reserve-at-acceptance** policy (resolves PRD §18 open question).
- Submit **blocks non-active requesters** (`access_status != ACTIVE` → rejected) — `workflow.py:55`.
- Public endpoints under HMAC-protected `public/`: checkin verify, submit, status. Admin queues + accept/reject with **404-before-403** scoping.
- `apps/checkin/` — fail-closed Check-In client: `verify()`, `CheckinUnavailable`→503 / `CheckinDenied`→403. `stub` vs `http` backend via `CHECKIN_MODE`; http config validated at boot. **Currently runs in stub mode.**
- `apps/inventory/availability.py` — Inventory Availability module: `reserve_for_request` (row-locked, never-below-zero, `InsufficientStock`). The only place reserve/available counts change.
- Tests: `test_request_workflow.py`.

### Phase 6 — Issue / Handover (`241dde6`)
- `workflow.py` gained `assign_box` + `issue_request`; transition `accepted → issued`.
- **Hard rule enforced:** cannot issue without a **box QR scan** AND an **issue photo**.
- `apps/boxes/` — `Box` model, immutable `BoxScan` records (with `context` incl. `"return"`). Box double-issue prevented by a **partial unique constraint** (`uniq_active_loan_per_box`). DB-level immutability triggers on scans.
- `availability.py` gained `issue_items` (reserved → issued movement).
- Admin endpoints: active-loans, assign-box, issue (404-before-403).
- Tests: `test_issue.py`, `test_boxes.py`.

### Public inventory (frontend)
- `frontend/src/features/inventory/` — `PublicInventoryPage`, `ProductCard`, `AvailabilityBadge`, TanStack Query hook + API client. This is the **only** frontend feature built.

---

## 3. What is IN FLIGHT — Return flow (uncommitted, tested)

**Status: implementation and behavior tests written, full backend suite passing, NOT committed.** This is ready for final review/QA and commit.

Plan: `docs/superpowers/plans/2026-06-11-return-flow.md` (Codex Stage-1 **approved**, Round 2).

**Uncommitted changes** (from `git status`):
- **Modular refactor** of the `hardware_requests` app (to honor the ~200-line file rule). The old monolithic `workflow.py`/`views.py` are now thin re-export shims:
  - **Workflow split:** `request_workflow.py` (submit/accept/reject), `handover_workflow.py` (assign-box/issue), `return_workflow.py` (return), plus shared `workflow_utils.py` (`locked_request`) and `workflow_errors.py` (exception types). `workflow.py` re-exports them so `from apps.hardware_requests import workflow` still works.
  - **Views split:** `public_views.py` (checkin/submit/status), `queue_views.py` (pending/accepted/active-loans), `review_views.py` (accept/reject), `handover_views.py` (assign-box/issue), and the return view, plus shared `view_helpers.py` (`request_queryset`, `ACTION_ERROR_RESPONSES`). `views.py` re-exports them.
  - **Models split:** `return_models.py` holds `ReturnEvent` + `RequesterAccountability`, re-exported from `models.py`.
- Modified: `hardware_requests/{exceptions,models,notifications,permissions,serializers,urls,views,workflow}.py`, `inventory/availability.py`.
- New migrations: `0003_requesteraccountability_returnevent.py`, `0004_return_records_immutable_triggers.py`.
- New plan doc.

**What the return flow does** (PRD §6.4, §6.5 partial):
- `POST /api/v1/admin/requests/:pk/return` (config mounts `apps.hardware_requests.urls` under `/api/v1/`; route at `urls.py:58`). Perm `CanReturnRequest` → `rbac.Action.RETURN_REQUEST`, which is in `_ADMIN_ACTIONS` but **not** `_GUEST_ADMIN_ACTIONS` (`rbac.py:46` vs `:50`) — so admin + superadmin only; guest admins **cannot** return in MVP per PRD §4.3.
- Scan returned box (must match `assigned_box`), attach mandatory **return photo + remark** (the §17 hard rule), resolve each item as **returned-good / damaged / missing**.
- Stock moves `issued → available | damaged | lost` via new `availability.return_items(...)`.
- Supports **multiple partial returns** via an immutable `ReturnEvent` per physical return; request lands in `partially_returned` until all units resolved, then `returned` (all good) or `closed_with_issue` (any damage/loss).
- Damage/loss creates immutable `RequesterAccountability` rows (per item, with `request_item` FK + quantity).
- New immutable models `ReturnEvent` + `RequesterAccountability` (model guards + DB triggers).

**Retention model decision (2026-06-11):** the append-only `AuditLog` is the *permanent* ledger of every lend/return. Loan rows + evidence/scan records may be purged by a future archival job (out of scope). No purge built now.

### ⚠️ Remaining work to close the return flow
1. **Tests written** — split across four files (mirroring the modular refactor) plus a shared `backend/tests/return_helpers.py` fixture module: `test_return_validation.py` (blank remark, missing photo, storage unavailable, scoped/wrong-type evidence without `object_exists`, box mismatch, negative/over-resolution, non-issued conflict), `test_return_outcomes.py` (good return, damaged/missing accountability, multi-item, partial vs `returned` vs `closed_with_issue`), `test_return_permissions.py` (guest-admin denial, cross-tenant 404-before-403, superadmin return), and `test_return_integrity.py` (immutability of `ReturnEvent`/`RequesterAccountability`, evidence reuse, `availability.return_items` insufficient-stock rollback).
2. **Full suite green** — run `.\\.venv\\Scripts\\python.exe -m pytest` from `backend/` (DB up) to confirm before commit.
3. **CLAUDE.md updated** — Project Status + source map now include return flow, `ReturnEvent`, `RequesterAccountability`, `availability.return_items`, and the `/return` endpoint.
4. **Still pending** — Stage 4 review, Stage 5 user QA, and commit with Claude/Codex co-authors.

---

## 4. What is LEFT — remaining phases (priority order)

### A. QR Codes & Assets module — **Phase 5 (mostly unbuilt)** — PRD §10, §13
The biggest backend gap. Only `Box` + `BoxScan` exist today. Still needed:
- `QrCode` model (per-makerspace namespace, `type: box|tool|asset`, `target_entity_*`, `status: active|revoked`, revocable/regenerable).
- `InventoryAsset` model (individually-tracked tools: `asset_tag`, `serial_number`, `status: available|reserved|issued|damaged|lost|retired|maintenance`).
- `QrScanEvent` generalization (today `BoxScan` covers box scans only; PRD wants `scan_context: issue|return|inventory_check|reassignment` across boxes + tools).
- Endpoints: `POST /admin/qr/boxes`, `POST /admin/qr/tools`, `POST /admin/qr/scan`, `GET /admin/qr/:id/print` (QR rendered via `segno`, print/download labels).
- Tool/asset QR scanning during issue/return (currently box-level only — issue & return both have a TODO seam for tool scans).
- **Test focus:** resolve/revoke, scan immutability, cross-tenant QR rejection, namespace isolation.

### B. Access restriction endpoints — **Phase 7 tail** — PRD §6.5
- The return flow *writes* `RequesterAccountability` rows, and submit *blocks* non-active users — but the **superadmin review → restrict/suspend → restore** action API is missing.
- Endpoints: `POST /admin/users/:id/restrict`, `POST /admin/users/:id/restore-access` (superadmin-only, audited: `user.access_restricted` / `user.access_restored`).

### C. Admin/superadmin REST CRUD surface — PRD §14 (currently Django-admin only)
There are **no REST endpoints** for these yet (managed via the themed Django admin instead). The PRD API surface expects them for the admin SPA:
- Makerspaces: `GET/POST /admin/makerspaces`, `PATCH /admin/makerspaces/:id`, Telegram group config.
- Inventory CRUD: `GET/POST /admin/makerspace/:id/inventory`, `PATCH /admin/inventory/:id` (public read exists; admin write does not).
- Staff management: `GET/POST /admin/users/admins`, `GET/POST /admin/users/guest-admins` (membership model exists; **no management API** — confirmed gap).
- Audit log read: `GET /admin/audit-logs` (filterable by makerspace/request/user/item/QR).
> Decide per-endpoint whether the SPA needs it or whether Django admin suffices for MVP. The PRD §15 dashboard tree assumes a custom SPA.

### D. Frontend — **Phase 8 + the admin/guest SPAs** — PRD §15
Only the public inventory page exists. Everything staff-facing is unbuilt:
- Adopt shadcn/ui + glass theme; per-makerspace branding.
- **Admin app:** dashboard (pending/accepted/active-loans/damaged), inventory CRUD, requests views, handover flow (assign box → scan → issue photo → mark issued), returns flow (search loan → scan → return photo → remark → resolve items), users, audit logs.
- **Guest-admin app:** accepted-requests queue, request detail, scan box, capture issue photo, confirm handover.
- **Public app:** add check-in verification + request form + request status (only browse exists).
- These depend on the REST endpoints in (C) existing first.

### E. Telegram integration — **Phase 9** — PRD §7, §9
- Currently only a notification **seam**: `hardware_requests/notifications.py` has three logging-only functions — `notify_request_submitted`, `notify_request_issued`, `notify_request_returned` — each called via `transaction.on_commit(...)` from the matching workflow step. No bot, no delivery.
- Per-makerspace `group_chat_id`; send request alerts; accept/reject callbacks **must route through `workflow.py`**, never mutate state directly.
- Verify Telegram actor authorization (`assertTelegramActorCan`).
- Endpoints: `POST /integrations/telegram/webhook`, `POST .../test-alert`.
- **Test focus:** callback→workflow parity with web, actor verification.

### F. Real Check-In API — **Phase 4 tail** — PRD §18
- HTTP backend scaffolding exists (`CHECKIN_MODE=http`, boot-validated) but runs in **stub** mode.
- **Open questions to resolve before building:** exact request/response shape; what field users enter (username/phone/QR/member id). Client must keep failing safe.

### G. API-first hardening — **Phase 10 (partial)** — PRD §14
- **Already done:** the `/api/v1/` prefix is mounted (`config/urls.py:16-20`) — hardware_requests, auth, evidence, and printing all live under `/api/v1/`; inventory is also reachable at the legacy unversioned `/api/` and at `/api/v1/` via a namespaced alias. drf-spectacular schema/Swagger/Redoc are wired.
- **Still needed:** **replace the browser-embedded HMAC secret** (`apps/apiclients/` + the Vite-baked `VITE_HMAC_SECRET`) with rate-limited public reads + a per-makerspace **publishable key**; add a per-tenant **CORS allowlist** (each makerspace registers its origin); publish a generated typed client (`openapi-typescript`/`orval`); audit that every `/api/v1/` route has a complete OpenAPI entry.
- Run the **OWASP security review skill** before merge.

### H. Bulk product import — **Phase 11 (not started)** — PRD "Later"
- Verified: **no `django-import-export` dependency** is installed (`requirements.txt` / `settings.py` clean) and no `unfold.contrib.import_export` is registered — nothing exists yet.
- To build: `django-import-export` + `unfold.contrib.import_export`; on-screen column-mapping wizard; upsert keyed on (`makerspace`, `name`); box-code column resolves to a real `Box` by `code`. Needs the **Box model slice** (done) and benefits from Phase 2 scoping (admins import only into assigned makerspaces).
- Lower priority; can slot in anytime after the admin surface exists.

---

## 5. Hard rules & invariants the next engineer MUST NOT regress

(From `CLAUDE.md` — these are enforced code, not convention.)
1. **`workflow.py` is the only place `HardwareRequest.status` changes.** Telegram/web/guest-admin all route through it.
2. **`availability.py` owns all quantity math.** Availability never goes below zero.
3. Cannot **issue** without box QR scan **and** issue photo. Cannot **return** without return photo **and** remark.
4. Issued qty ≤ accepted qty (unless admin/superadmin override).
5. Guest admins: may issue accepted requests; **cannot** accept/reject, edit inventory, manage QR, or (in MVP) return.
6. Evidence photos + QR/box scan records are **immutable**; audit logs are **append-only** (model guards + Postgres triggers).
7. Every admin/guest query is **makerspace-scoped**; every state-changing endpoint emits an **audit log**; cross-tenant access returns **404-before-403**.
8. Public inventory never exposes locations, box IDs, QR codes, scan history, evidence, requester history, or hidden counts.

## 6. Process the next engineer must follow

Per `~/.claude/CLAUDE.md`, every task runs the gated workflow:
**Stage 1** plan → Codex review (`/run-codex Review this plan: …`) → user approval → **Stage 2** Codex implements (Claude verifies) → **Stage 3** tests → **Stage 4** background Codex review (`/run-codex review`) → **Stage 5** user QA → **Stage 6** report + commit (Claude + Codex co-authors).
File modularity target ~200 lines (hard ceiling ~300); document every endpoint in OpenAPI.

## 7. Suggested build order from here

1. **Finish the return flow** (tests → review → QA → commit). *In flight.*
2. **Access restriction endpoints** (small, completes the §6.5 accountability loop already half-built).
3. **QR/Asset module (Phase 5)** — unblocks tool-level tracking and the print/scan UX.
4. **Admin REST CRUD surface (C)** — unblocks the frontend.
5. **Admin + guest-admin frontend (Phase 8)**.
6. **Telegram (Phase 9)** and **real Check-In (F)** — can run in parallel once workflow seams are stable.
7. **API hardening (Phase 10)** before any third-party makerspace onboards.
8. **Bulk import (Phase 11)** — opportunistic.

## 8. Local dev quick reference

```bash
docker compose up -d db                 # + minio for evidence
cd backend && pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo
python manage.py runserver               # http://localhost:8000  (docs at /api/docs/)
cd frontend && npm install && npm run dev # http://localhost:5000  (public page: /m/tinkerspace)
cd backend && pytest                     # DB must be up
```
