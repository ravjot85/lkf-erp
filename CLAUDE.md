# LKF ERP — Claude Session Context

## Project
**Lovely Knitfab Pvt Ltd** — Internal ERP for textile manufacturing.
Single-file Streamlit app: `lkfapp.py` (~5,800 lines).
Backend: Firebase Firestore (database) + Firebase Storage (files).

---

## Tech Stack
- **Python + Streamlit** (v1.32.0+) — all UI and logic in one file
- **Firebase Firestore** — NoSQL cloud database
- **Firebase Storage** — PDF and image storage
- **Google Drive API** — legacy file storage (old POs still reference Drive)
- **ReportLab** — PDF generation
- **Plotly + Pandas** — charts and data tables
- **Credentials:** `firebase-key.json` (service account)
- **Firebase project:** `lkf-erp-12c7d`
- **Theme:** camel/brown (`#B5804E` primary)

---

## Business Domain
Textile knitting factory. Tracks orders from PO → Knitting → External Processing (dyeing/washing) → Inward → Packing → Dispatch.

---

## Menu Structure
```
Dashboard
Forms:    PO | Shoot Order | Process Out | Process Inward | Packing | Cancel Order
Reports:  All Orders | Pending (STRIPE/PLAIN) | In Production | Cancelled |
          Customer Report | Customer Pending | Pending Drill-Down | Processing Report |
          Part Dispatched | In House
Masters:  Customer Master | Item Master | Processor Master
Edits:    Edit PO | Edit Packing List | Delete Packing List |
          Edit Process Out | Edit Process Inward | Cancel Shoot Order
```

---

## Firestore Collections

| Collection | Doc ID | Key Fields |
|---|---|---|
| `po` | `{OrderId}` | OrderId, Date, `Customer name`, customerpono, Item, Category (STRIPE/PLAIN), gsm, facricqnty, fabricprice, accessoryqnty, accessoryprice, coloursinstructions, accessory, pdf_url, image, image_drive_id |
| `shoot_order` | auto | OrderId, Date, `Customer name`, Item, Category, gsm, facricqnty, accessoryqnty, coloursinstructions, accessory, image, image_drive_id, pdf_url |
| `process_out` | `{ChallanNo}_{LotNo}_{index}` | ChallanNo, Date, PartyName, GstNo, VehicleNo, LotNo, OrderId, `Customer name`, Item, Colour, Roll, Qnty, Process, DiaGsm |
| `process_inward` | `{ChallanNo}_{LotNo}` | ChallanNo, Date, PartyName, VehicleNo, LotNo, OrderId, `Customer name`, Item, Colour, Process, SentRoll, SentQty, ReceivedRoll, ReceivedQty, ShortQty, ShortPct, Rate, Amount, Remarks, **ProcessOutDocId**, pdf_url |
| `PackingListRaw` | `{RawId}` | RawId (auto-int), Date, OrderId, `Customer name`, Item, FabricDetails, AccessoryDetails, pdf_url |
| `cancel_orders` | `{OrderId}_{Date}` | OrderId, Date, Customer, Item, Reason, Status (VALID/INVALID) |
| `customer_master` | `{CustomerName}` (uppercase) | CustomerName |
| `item_master` | `{ItemName}` (uppercase) | ItemName |
| `processor_master` | `{ProcessorName}` (uppercase) | ProcessorName, GstNo |
| `counters` | `po_order_id` | last_id (atomic int) |

> **Note:** Firestore field is `"Customer name"` (with space) — not `"Customer"` or `"CustomerName"`.
> In DataFrames it is normalised to `Customer` and `CustomerNorm` (no spaces, uppercase).

---

## OrderId — Complete Flow

### Generation (PO submit)
- Atomic Firestore transaction on `counters/po_order_id → last_id`
- First call: scans all `po` docs to find current max, sets counter
- Returns plain string e.g. `"1928"` — always purely numeric
- PO stored as `po/{OrderId}` (OrderId = document ID)
- Only assigned at submit — never pre-filled

### Through Workflow
1. **PO** — OrderId created, doc stored in `po/`
2. **Shoot Order** — user types OrderId → fetches `po/{OrderId}` → auto-fills fields → saved in `shoot_order` with OrderId field
3. **Process Out** — user types Lot No (e.g. `1001A`, `1122-D`) → `extract_order_id()` strips leading digits → `"1001"` → fetches PO → saved in `process_out` with LotNo + OrderId
4. **Process Inward** — dropdown shows pending lots from `process_out` for selected party → user picks lot → saved in `process_inward` with `ProcessOutDocId` linking to exact process_out doc
5. **Packing** — user types OrderId (with or without suffix) → tries exact PO match, falls back to base numeric match → saved in `PackingListRaw`

### Status Derivation (`_load_status_df()`)
Status is **never stored** — computed fresh each load by checking collection membership:
```
cancel_ids  (cancel_orders where Status != INVALID)  → "Cancelled"
pack_ids    (PackingListRaw base OrderIds)            → "Dispatched"
proc_in_ids (process_inward OrderIds)                → "In House Finishing/Packing"
proc_out_ids (process_out OrderIds)                  → "On Dyeing/Washing (PartyName)"
shoot_ids   (shoot_order OrderIds)                   → "Knitting"
else                                                 → "Pending"
```

---

## Packing List — Suffix Logic

- OrderId in PackingListRaw can be `"1001"`, `"1001A"`, `"1001B"` etc.
- **PO lookup:** tries `po/{oid}` exact first; if not found strips to base digits `r'^(\d+)'` and tries `po/{base}`
- **Duplicate check:** exact string match on `PackingListRaw.OrderId` — blocks if already exists, prompts to use suffix
- **Status aggregation:** `_base_oid()` maps all suffixed IDs to base → `"1001A"` + `"1001B"` both make order `"1001"` show as Dispatched
- **PDF merge:** on each new slip, fetches ALL slips with exact same OrderId string, merges FabricDetails + AccessoryDetails by colour, generates one combined PDF, updates `pdf_url` on all those slips

### FabricDetails / AccessoryDetails format
Multi-line string, one colour per line:
```
RED: 12.5,13.0,11.8
BLUE: 10.0,9.5
```
Parsed everywhere by splitting on `:` then `,`.

---

## Process Out — Key Details

- **ChallanNo:** scan `process_out` for max numeric ChallanNo (floor 100) + 1
- **LotNo → OrderId:** `re.match(r"^(\d+)", lot_no)` — leading digits only
- **Doc ID:** `{ChallanNo}_{LotNo}_{index}` — index prevents overwrite if same LotNo appears twice in one challan
- Header fields (ChallanNo, Date, PartyName, GstNo, VehicleNo) merged into **every lot doc**
- **No file storage** — challan is HTML rendered inline with browser Print button
- GstNo fetched fresh from `processor_master` at save time

---

## Process Inward — Key Details

- **ChallanNo:** scan `process_inward` for max numeric ChallanNo (floor 100) + 1
- **Doc ID:** `{ChallanNo}_{LotNo}` — potential collision if same LotNo in same challan twice
- **PDF stored on Google Drive** (not Firebase Storage) — uses `PROC_IN_PDF_FOLDER` Drive folder ID
- **ProcessOutDocId** field stored on each inward lot — critical for exact receipt matching

### Pending Lot Calculation (two-tier)
**Tier 1 — Exact match (new records):**
If inward record has `ProcessOutDocId`, sum received qty against that specific process_out doc ID.
If `received < sent` → still pending.

**Tier 2 — Waterfall (legacy records without ProcessOutDocId):**
Group by LotNo. Run exact-qty match first to claim receipts. Remaining receipts applied chronologically (by date + doc_id order) across entries.

---

## Shared Data Loading

`_load_status_df()` — cached 10 minutes, used by Dashboard + all Reports:
- Loads po, shoot_order, process_out, process_inward, PackingListRaw, cancel_orders
- Returns single DataFrame with columns: OrderId, CustomerPoNo, Customer, CustomerNorm, Item, ItemNorm, Category, Date, ShootDate, DispatchDate, GSM, FabricQty, FabricPrice, AccQty, AccPrice, PackedFabricQty, PackedAccQty, Status, pdf_url, image_drive_id, image_url, Accessory
- **Orphan packing rows:** PackingListRaw entries with no matching PO (e.g. OrderId `"LK101"`) are added as extra rows with Status "Dispatched" and empty price/GSM fields

---

## Customer Report — Special Rules
- Dropdown populated **only from `customer_master`** — not from order data
- Shows In Production / Pending / Dispatched (optional) sections
- Filters: date range (All / This Month / Custom), Order ID search, Customer PO No search

---

## Masters — Cascading Rename
When a Customer / Item / Processor name is changed in Masters:
- Updates the master doc itself
- Batch-updates all dependent collections (po, shoot_order, process_out, process_inward, PackingListRaw, cancel_orders)
- Clears `_load_status_df` cache after

---

## Google Drive Folder IDs (hardcoded)
```
Shared Drive root:   0AAXVNV0_tBbqUk9PVA
PO images:           1EsVdPRfOX6qW3EqkV9ohOc3z8yXCkazU
PO PDFs:             1B5vthuV61a3h1F1nOg7v0x966uyGaiAX
Shoot PDFs:          1-6oYnJjFagl1Grvbx-Ji6rI0yD49mqgG
Process Out PDFs:    1OWzxNkDhCEpoM_PUwQzJH-EePvP_SSt6
Process Inward PDFs: 1CFRfp8ctHKuawja-yxruaSTLV1wn7W3p  (PROC_IN_PDF_FOLDER)
Packing PDFs:        1Yk7mw4PYBviU9c8F5d6IzMTs21syQVrg
```
New files go to Firebase Storage. Drive used for Process Inward PDFs and legacy PO images.

---

## Common Pitfalls
- Field name is `"Customer name"` (space) in Firestore — always use this exact string
- `facricqnty` (typo in original data) — not `fabricqty`
- `gsm` (lowercase) in Firestore — not `GSM`
- `customerpono` (all lowercase) — not `CustomerPoNo`
- Process Out ChallanNo auto-increment is from session_state after first load — do not call `get_next_proc_out_challan_no()` on every rerun
- `_load_status_df()` is cached — always call `.clear()` after writes that affect status
- CustomerNorm = `Customer name.upper().strip().replace(" ", "")` — used for matching, not display

## DOM / JavaScript Rules — CRITICAL
- **NEVER use `element.remove()` or `removeChild()` on DOM nodes React manages.** This causes `NotFoundError: removeChild` crashes during React reconciliation. Use `element.style.display = 'none'` or CSS `display:none !important` instead.
- **Clear (×) buttons are hidden via CSS** (`button[aria-label*="clear" i]`) — do not add JS to remove them.
- **`components.html()` MutationObservers must use a once-only guard** (e.g. `if (par._lkfPONavReady) return`) — Streamlit reruns re-inject the script each time, accumulating multiple observers that fight React.
- **Enter-key nav JS must use `e.preventDefault()` + `e.stopPropagation()`** — without these, Enter triggers a Streamlit rerun causing screen dimming and lost focus.
- **Debounce MutationObserver callbacks** (60–80ms `setTimeout`) so they never fire mid React reconciliation.

---

## Helper Scripts
- `migrate_pdfs_to_firebase.py` — one-time migration of Drive PDFs to Firebase Storage
- `link_pdfs.py` / `link_shoot_pdfs.py` — link existing Drive PDF URLs to Firestore records
- `rename_customer.py` — standalone cascading customer rename utility
