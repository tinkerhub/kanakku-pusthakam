# Project Handover - Makerspace Manager

**Date:** 2026-06-11
**Audience:** Codex, Claude, and any engineer picking up the build
**Purpose:** Current source of truth for what is built, what is verified, and what remains as hardening or polish.

Read this alongside:
- `docs/prd-architecture.md`
- `docs/roadmap.md`
- `CLAUDE.md`

## 1. Current Status

The core MVP is now implemented end to end. Public users can browse inventory, verify through Check-In, submit requests, and check status. Staff can accept/reject, assign boxes, issue with evidence, return with evidence and per-item outcomes, record accountability, restrict/restore users, manage inventory, create and scan QR labels, import products in bulk, receive Telegram notifications, and use first-pass Space Manager (`/admin`) and Guest Admin frontend panels.

| Layer | State |
|---|---|
| Backend lending pipeline | Built and tested: submit -> accept/reject -> assign box -> issue -> partial/full return -> accountability |
| QR/assets module | Built: `QrCode`, immutable `QrScanEvent`, `InventoryAsset`, box/product/asset QR endpoints |
| Admin REST CRUD | Built: makerspaces, inventory, users/staff, audit logs |
| Access restriction | Built: superadmin-only restrict/restore endpoints, audited |
| Telegram | Built MVP: delivery, test alert, webhook callbacks routed through workflow |
| Check-In API | Built: stub + HTTP mode with API-key support and fail-safe behavior |
| Frontend | Built first pass: public inventory, Space Manager panel, Guest Admin panel |
| API hardening | Built MVP: `/api/v1/`, publishable keys, per-makerspace CORS origins, public read throttles, browser HMAC removed from frontend |
| Bulk import | Built: preview/apply workflow with row-level validation and scoped box-code resolution |

## 2. Completed Backend Phases

### Phase 1 - Admin Theme + Public Frontend
- Django admin uses django-unfold.
- Frontend dev server runs on port 5000.

### Phase 2 - Auth + RBAC
- Custom `User` model with global role and `access_status`.
- `MakerspaceMembership` grants per-makerspace Space Manager, Inventory Manager, Guest Admin, and Print Manager roles.
- Inventory Manager is membership-only: it can run the full hardware lifecycle, including inventory edits, accept/reject, assign box, issue, return, evidence upload, QR management, and audit viewing, but cannot manage printing, staff, or makerspace settings.
- `apps.accounts.rbac` owns action checks and makerspace scoping.
- JWT login/refresh/logout/me are mounted under `/api/v1/auth/`.

### Phase 3 - Evidence + Audit
- `EvidencePhoto` stores immutable private object-storage evidence rows.
- `AuditLog` is append-only at model and DB-trigger level.
- Evidence upload/view endpoints are mounted under `/api/v1/admin/`.
- Evidence upload/view endpoints gate on per-makerspace `UPLOAD_EVIDENCE` plus active account status, not global staff roles.

### Phase 4 - Request Workflow
- Public check-in verify, submit, and request-status endpoints exist.
- Admin pending/accepted queues and accept/reject endpoints exist.
- Reserve-at-acceptance is enforced through `apps.inventory.availability`.

### Phase 5 - QR Codes & Assets
- `apps.boxes.models.QrCode` stores active/revoked QR payloads for `box`, `product`, and `asset` targets.
- `apps.boxes.models.QrScanEvent` records immutable generalized scans with contexts: `issue`, `return`, `inventory_check`, `reassignment`.
- `apps.inventory.models.InventoryAsset` tracks individual assets with status, asset tag, serial number, product, and optional box.
- Endpoints:
  - `POST /api/v1/admin/qr/boxes`
  - `POST /api/v1/admin/qr/tools`
  - `POST /api/v1/admin/qr/scan`
  - `GET /api/v1/admin/qr/:id/print`
  - `POST /api/v1/admin/qr/:id/revoke`
- QR management checks both `MANAGE_QR` and active account status.
- Tests: `backend/tests/test_qr_api.py`.

### Phase 6 - Issue / Handover
- `assign_box` and `issue_request` live in workflow services.
- Issue requires assigned/scanned box and uploaded issue evidence.
- Stock moves reserved -> issued through `availability.issue_items`.

### Phase 7 - Return Flow + Access Restriction
- Return flow is committed in `951ffa6`.
- The hardware request app is split into modular workflow/view/model files with thin shims.
- Return requires matching box scan, uploaded return evidence, remark, and per-item resolution.
- Stock moves issued -> available/damaged/lost through `availability.return_items`.
- Immutable `ReturnEvent` and `RequesterAccountability` rows are enforced by model guards and DB triggers.
- Superadmin endpoints:
  - `POST /api/v1/admin/users/:id/restrict`
  - `POST /api/v1/admin/users/:id/restore-access`
- Tests:
  - `test_return_validation.py`
  - `test_return_outcomes.py`
  - `test_return_permissions.py`
  - `test_return_integrity.py`
  - `test_admin_api.py`

### Phase 8 - Staff Frontend
- `frontend/src/features/staff/` provides first-pass Space Manager and Guest Admin panels.
- Routes:
  - `/admin`
  - `/guest-admin`
- Included screens: login, request queues, accept/reject, assign box, issue, return, inventory table, bulk import preview/apply, QR tools, user counts, audit log list.
- Staff user counts use `/api/v1/admin/users/space-managers`, `/api/v1/admin/users/inventory-managers`, `/api/v1/admin/users/guest-admins`, and `/api/v1/admin/users/print-managers`.

### Phase 9 - Telegram
- `apps.integrations.telegram.send_message(...)` delivers via Telegram Bot API when configured.
- Hardware request notification hooks now call Telegram after submit/issue/return.
- Webhook callbacks accept/reject requests through `workflow.accept_request` and `workflow.reject_request`.
- `User.telegram_user_id` links Telegram actors to staff accounts.
- Endpoints:
  - `POST /api/v1/integrations/telegram/webhook`
  - `POST /api/v1/integrations/telegram/test-alert`
- Tests: `backend/tests/test_telegram_integration.py`.

### Phase 10 - API Hardening
- `/api/v1/` is the primary API namespace.
- Public frontend no longer embeds HMAC client secrets.
- `Makerspace.public_api_key` supports publishable browser keys via `X-Publishable-Key` or `?key=`.
- `Makerspace.cors_allowed_origins` provides per-tenant public-origin allowlists.
- Public reads use the `public_read` throttle scope.
- Existing HMAC middleware remains backward-compatible for deployments still using registered API clients.

### Phase 11 - Bulk Product Import
- `apps.admin_api.bulk_import` implements a preview/apply import flow.
- Inputs: uploaded file or structured rows.
- Supported formats: CSV, TSV, JSON, and XLSX when `openpyxl` is installed.
- Validation:
  - required `name`, `total_quantity`, `available_quantity`
  - non-negative quantity buckets
  - bucket sum cannot exceed total
  - valid `tracking_mode`
  - valid `public_availability_mode`
  - `box_code` must resolve to a `Box` in the target makerspace
- Apply behavior: upsert by `(makerspace, name)`.
- Audit action: `inventory.bulk_imported`.
- Tests: `backend/tests/test_admin_api.py`.

## 3. Remaining Hardening / Polish

No core roadmap phase is intentionally left as "not started." The remaining work is production hardening:
- Install `openpyxl` in environments that require XLSX uploads.
- Add a generated external TypeScript SDK from OpenAPI if third-party consumers need a packaged client.
- Add Telegram webhook secret-token validation before public deployment.
- Replace prompt-based staff UI actions with dedicated forms and evidence-upload flows.
- Expand admin frontend CRUD forms beyond the first-pass operational panels.
- Run a formal OWASP/API review before onboarding external makerspaces.

## 4. Hard Rules To Preserve

1. `workflow.py` and its modular re-exported services remain the only place `HardwareRequest.status` changes.
2. `availability.py` owns all quantity math.
3. Issue requires box scan + issue photo.
4. Return requires return photo + remark.
5. Guest Admins may issue accepted requests but cannot accept/reject, edit inventory, manage QR, or return.
6. Inventory Managers may run the full hardware lifecycle but cannot manage printing, staff, or makerspace settings.
7. Evidence endpoints require per-makerspace `UPLOAD_EVIDENCE` plus active status; QR management requires active status.
8. Evidence photos, scan records, return events, accountability records, and audit logs are immutable/append-only where applicable.
9. Space Manager, Inventory Manager, Guest Admin, and Print Manager queries must be makerspace-scoped.
10. Cross-tenant object access must return 404 before 403 where object existence would otherwise leak.
11. Public inventory must not expose storage locations, box IDs, QR codes, scan history, evidence, requester history, or hidden counts.

## 5. Verification

Latest verification run:

```bash
cd backend
.\\.venv\\Scripts\\python.exe -m pytest
# 194 passed, 14 existing JWT key-length warnings

cd ..\\frontend
npm run build
# TypeScript + Vite production build passed
```

Docker verification:

```bash
docker compose up -d db minio createbuckets
docker compose build backend frontend
docker compose run --rm backend python manage.py check
docker compose run --rm backend pytest
# 162 passed, 14 existing JWT key-length warnings
docker compose run --rm backend python manage.py makemigrations --check --dry-run
docker compose run --rm backend python manage.py spectacular --validate --file /tmp/openapi.yaml
docker compose up -d backend frontend
# Frontend /, backend /docs/, /schema/, and /api/public/makerspaces/ returned 200
```

Also run before merge:

```bash
cd backend
.\\.venv\\Scripts\\python.exe manage.py check
.\\.venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run
```

## 6. Local Dev Quick Reference

```bash
docker compose up -d db
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver

cd frontend
npm install
npm run dev
```

Useful URLs:
- Public inventory: `http://localhost:5000/m/tinkerspace`
- Admin panel: `http://localhost:5000/admin`
- Guest-admin panel: `http://localhost:5000/guest-admin`
- API docs: `http://localhost:8000/docs/`
