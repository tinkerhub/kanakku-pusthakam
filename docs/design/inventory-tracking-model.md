# Inventory Tracking Model — Design

**Status:** awaiting user sign-off. **Decisions locked (2026-06-07):** hybrid tracking (individual units + quantity), nested boxes, full custody log, products have no `image_url`.

This is the source of truth for the QR/Box + individual-unit + custody/evidence redesign. It supersedes the simpler "Box model slice" note in `roadmap.md`.

## Why this exists

Hardware must be traceable per physical item: each microcontroller/SBC lives in its **own small QR box**; tools (screw boxes, etc.) are QR-tagged; small boxes are placed inside **larger handout boxes**. At handout an admin **scans the QR and captures a photo + remark**; same on return. The next person must be able to see **who had an item last**.

## Layers & entities

### 1. Catalog — `InventoryProduct` (existing, adjusted)
The item *type* or a quantity-counted consumable.
- **Remove `image_url`.**
- Add `tracking_mode`: `quantity` | `individual`.
  - `quantity` → consumables (filament, loose screws); keep the existing quantity buckets (`total/available/reserved/issued/damaged/lost`).
  - `individual` → represented by `Unit` records (quantity is the count of its available Units).
- Keeps public-visibility fields (`is_public`, `show_public_count`, `public_availability_mode`).

### 2. Containers — `Box` (built flat; extend)
A QR-tagged container.
- Existing: `makerspace`, `code` (globally-unique opaque QR payload), `label`, `location`, `description`, `is_active`.
- **Add `parent`** = self-FK (`null=True`, `on_delete=SET_NULL`, `related_name="children"`) → nesting: a small board-box sits inside a larger handout box. Same model at every level.
- Guard: a box's `parent` must be in the same makerspace (model `clean()`), and a box cannot be its own ancestor (no cycles).

### 3. Items — `Unit` (new)
One individually-tracked physical instance (a specific board / a specific tool).
- `makerspace` FK; `product` FK → `InventoryProduct` (its type); `box` FK → `Box` (current container, nullable, same-makerspace validated); `asset_tag` (human label, optional).
- `status`: `available | issued | damaged | lost | maintenance | retired`.
- The board's QR **is its small box** — scanning the box resolves `box.units`. (A Unit may also carry its own code later if needed.)
- Tools are Units (`product` whose category = tool).

### 4. Custody + evidence — `CustodyEvent` (new, immutable, append-only)
One handover record.
- `unit` FK; optional `box` FK (context — which box was scanned/handed); `action`: `issue | return`.
- `actor` FK → User (the admin performing it); `holder` → who physically took it (User; free-text fallback until the requester flow exists).
- `occurred_at`; `photo` (evidence — **required**); `remark` (text — **required**).
- Records are never edited/deleted. **"Who had it last"** for a unit = the `holder` of its latest `CustodyEvent`.

## Flows

- **Handout (issue):** admin scans the small box QR(s) → resolves the Unit(s) → hands out the larger box that contains them → one `CustodyEvent(issue)` per unit with photo + remark → unit `status = issued`.
- **Return:** scan box/unit QR → `CustodyEvent(return)` with photo + remark → unit `status = available` (or `damaged`/`lost`).
- **History:** the `CustodyEvent` list for a unit is its full custody trail; latest = current/last holder.

## Modeling choices (defaults; flag if you disagree)

1. **Custody attaches to `Unit`** (the thing lent). Handing out a large box = a `CustodyEvent` per contained unit. (Not box-level custody.)
2. **`holder` is a User** for now (ties into `access_status` later); free-text allowed until the request workflow (Phase 4) formalizes requesters.
3. **`photo` = Django `ImageField`** (local `media/`) for now; migrate evidence to object storage (MinIO) in Phase 3. Photos are private, never on the public API.

## Build slices (revised; each goes through the gate)

- **S1 — Product cleanup:** remove `image_url` (model + migration + public serializer + frontend `ProductCard`/types); add `tracking_mode`.
- **S2 — Box nesting:** add `Box.parent` + same-makerspace/no-cycle validation + admin tree display.
- **S3 — Unit:** model + admin (filters, box assignment, status), scoped to makerspace.
- **S4 — Custody + evidence:** `CustodyEvent` model (photo + remark), "last holder" surfaced on the Unit/Product admin, immutability enforced.
- **Later (Phases 4/6):** the scan-during-handout UI and request workflow that *create* CustodyEvents through the workflow service; evidence → object storage (Phase 3).

## Out of scope here
QR *scan history* as a separate log, tool/asset maintenance scheduling, and the public-facing changes beyond removing `image_url`.
