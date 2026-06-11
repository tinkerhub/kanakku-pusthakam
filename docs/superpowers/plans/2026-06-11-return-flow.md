# Plan - Return Flow

**Phase:** Return / Accountability (PRD sections 6.4, 6.5 partial, 11, 13, 14, 17)
**Follows:** Issue/Handover (`241dde6`)
**Scope:** box-level scanning only; tool/asset QR remains deferred.

## Goal

Let staff process an issued loan return with traceability:
- scan the returned box and require it to match the assigned box.
- attach a mandatory return photo and non-blank remark.
- resolve outstanding quantities as returned-good, damaged, or missing.
- move stock from issued to available, damaged, or lost.
- create accountability rows for damage/loss.
- support multiple partial returns through one immutable event per physical return.

Terminal status is `returned` when all resolved units are good, or
`closed_with_issue` when any unit is damaged/missing. Otherwise the loan remains
`partially_returned`.

## Retention Decision

The append-only `AuditLog` is the permanent ledger for every lend/return. Its
`target_id` is a string, so it survives future loan deletion. Loan rows plus
evidence/scan records may be purged by a future archival job. No purge or extra
delete-blocking is built in this phase.

## Data Model

`ReturnEvent`:
- FK `request` to `HardwareRequest` with `PROTECT`.
- FK `makerspace` with `PROTECT`.
- FK `box` with `PROTECT`; required because return scan is mandatory.
- OneToOne `evidence` to `EvidencePhoto` with `PROTECT`.
- `remark`, `actor`, `created_at`.
- immutable in model methods and database triggers.

`RequesterAccountability`:
- FK `requester`, `request`, `request_item`, `makerspace`.
- `issue_type`: `damaged` or `missing`.
- `description`, optional `evidence_photo`, `quantity`, `created_by`, `created_at`.
- immutable in model methods and database triggers.

Migrations:
- `0003_requesteraccountability_returnevent.py`
- `0004_return_records_immutable_triggers.py`

## Availability

`apps/inventory/availability.py` owns `return_items(request, resolutions)`.
It must run inside `transaction.atomic()`, lock products by pk, and for each
resolution:
- reject movement if `issued_quantity` is too low.
- decrement issued by returned + damaged + missing.
- increment available by returned, damaged by damaged, lost by missing.
- increment the request item counters.

No other module may do return quantity math.

## Workflow

`apps/hardware_requests/workflow.py` remains the public facade. The return
implementation lives in smaller return-focused modules.

`return_items(actor, request, evidence_id, remark, box_code, resolutions)`:
- strip and require `remark`.
- scope evidence to request makerspace and `evidence_type="return"` before any
  storage `object_exists` call.
- raise `EvidenceNotUploaded` when the object is missing and propagate
  `StorageUnavailable`.
- lock the request and require status `issued` or `partially_returned`.
- resolve the scanned box in the request makerspace and require it to match
  `assigned_box`.
- create immutable `BoxScan(context="return")`.
- validate each resolution belongs to this request and does not exceed remaining
  issued quantity.
- require at least one resolved unit.
- call `availability.return_items`.
- create immutable `ReturnEvent`; OneToOne evidence reuse maps to 400.
- create `RequesterAccountability` rows for damaged/missing quantities.
- audit `item.damaged`, `item.missing`, `request.returned`,
  `request.partially_returned`, `request.closed_with_issue`,
  `evidence.attached`, and `box.scanned`.
- notify through `notify_request_returned` on commit.

## API

Endpoint:
- `POST /api/v1/admin/requests/:pk/return`

Permission:
- `CanReturnRequest`
- admin and superadmin only in MVP.
- guest admins cannot return.
- cross-tenant access stays 404-before-403.

Serializer:
- `ReturnItemResolutionSerializer`: `item_id`, `returned`, `damaged`, `missing`.
- `ReturnRequestSerializer`: `evidence_id`, `box_code`, non-blank `remark`,
  non-empty `resolutions`.
- reject duplicate `item_id` and all-zero rows.

Response coverage:
- 400 validation errors.
- 403 permission errors.
- 404 scoped not found.
- 409 invalid transition or missing evidence upload.
- 503 storage unavailable.

## Tests

Storage is mocked. Tests are split by behavior:
- validation: blank remark, missing photo, storage down, scoped/wrong-type
  evidence without storage call, box mismatch, over-resolution, non-issued loan.
- outcomes: full good return, damaged/missing closure, multi-item accountability,
  partial-then-complete return.
- permissions: guest-admin denial, cross-tenant 404, superadmin success.
- integrity: immutable `ReturnEvent`/`RequesterAccountability`, evidence reuse,
  insufficient issued stock guard.

## Docs

`CLAUDE.md` and `docs/HANDOVER.md` must describe the return flow, return models,
`availability.return_items`, and `/return` endpoint.

## Risks

- `object_exists` intentionally runs before acquiring the request lock.
- Partial returns are event-sourced through `ReturnEvent`; item counters are the
  running totals.
- `uniq_active_loan_per_box` keeps the box occupied through `partially_returned`
  and frees it at `returned`/`closed_with_issue`.

## Revision Log

- Round 1 review added `request_item` to accountability rows and made
  `ReturnEvent.box` required.
