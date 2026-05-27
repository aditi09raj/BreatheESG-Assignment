# Data Model

## Why this matters more than the UI

Every design decision in this model is load-bearing. ESG data gets scrutinised by external auditors, by regulators, and eventually by the public. A record that can't prove its origin, unit conversion, or approval chain is worthless. The model encodes those requirements directly.

---

## Entity overview

```
Tenant
  └─ DataSource (SAP_FUEL | UTILITY_ELECTRICITY | TRAVEL)
       └─ IngestionRun (one per file upload)
            └─ RawRecord (one per source row, immutable after creation)
                 └─ EmissionRecord (normalised, reviewable, auditable)
                      └─ EmissionRecordEdit (append-only audit log)
```

---

## Tenant

Multi-tenancy is handled at the `Tenant` model level. Every `DataSource` and `EmissionRecord` has a foreign key to `Tenant`. In a production deployment, all API queries would filter on `request.user.profile.tenant`. The prototype uses a single tenant (Acme Manufacturing GmbH) to stay focused on the ingestion and review flows.

**What I didn't do:** row-level security via Postgres RLS or Django's `django-guardian`. That would be the right move for a real multi-tenant SaaS, but it's scope I explicitly didn't build (see TRADEOFFS.md).

---

## DataSource

Represents a configured ingestion channel — not a single file, but a persistent data source the client has.

| Field | Purpose |
|-------|---------|
| `source_type` | `SAP_FUEL`, `UTILITY_ELECTRICITY`, or `TRAVEL` — drives which parser is used |
| `name` | Human-readable: "SAP MM — Fuel & Procurement (DE/UK Plants)" |
| `description` | Where this comes from and how it's configured |

The source type is fixed at create time. If a client has two SAP plants with incompatible column layouts, they get two DataSource records, not one. That's correct: the parser configuration belongs to the source, not the file.

---

## IngestionRun

One record per file upload. This is the entry point into the lineage chain.

| Field | Purpose |
|-------|---------|
| `file_hash` | SHA-256 of the uploaded content. Used to detect duplicate uploads before parsing begins — not after. A hash collision on different files is astronomically unlikely; a re-upload of the exact same file would create a duplicate IngestionRun and duplicate EmissionRecords, which is a real problem. The hash check prevents this. |
| `status` | `PENDING → PROCESSING → COMPLETED / FAILED`. Parsers are synchronous in this prototype; in production this would be a Celery task and the status would be polled or websocket-pushed. |
| `error_summary` | JSON array of up to 20 per-row parse errors. The full error detail lives on `RawRecord.parse_errors`. |
| `records_total / records_parsed / records_failed` | Counts updated at end of run. `records_total = records_parsed + records_failed` is not always true — skipped rows (personal expenses, non-consumption movement types) are neither parsed nor failed. |

---

## RawRecord

**Immutable after creation.** This is the verbatim source row.

| Field | Purpose |
|-------|---------|
| `row_index` | 1-based line number in the source file. Auditors can open the original file and find this row. |
| `raw_data` | JSON: every key-value pair as it appeared in the file, before any normalisation. German decimal commas, inconsistent unit codes, German column headers — all preserved. |
| `parse_status` | `OK`, `FAILED`, or `SUSPICIOUS`. `SUSPICIOUS` means parsing succeeded but something looks wrong (e.g. estimated utility read, unknown material type). `SUSPICIOUS` rows automatically get `FLAGGED` review status on the resulting `EmissionRecord`. |
| `parse_errors` | For `FAILED` rows: the error message(s). For `SUSPICIOUS` rows: the reason(s) for flagging. |

The raw record is never modified. If an analyst corrects a value in the `EmissionRecord`, the correction is recorded in `EmissionRecordEdit` and the original `raw_data` remains the source of truth for what came out of the client's system.

---

## EmissionRecord

This is where normalisation happens. The key design choices:

### Scope 1 / 2 / 3 categorisation

| Source | Scope | GHG Protocol Category |
|--------|-------|----------------------|
| SAP fuel (diesel, petrol, gas) | 1 | Stationary combustion |
| Utility electricity | 2 | Purchased electricity |
| Corporate travel — flights | 3 | Category 6: Business travel |
| Corporate travel — hotels | 3 | Category 6: Business travel |
| Corporate travel — car rental | 3 | Category 6: Business travel |
| Corporate travel — rail | 3 | Category 6: Business travel |

SAP procurement (non-fuel goods) would be Scope 3 Category 1 (Purchased goods and services) — that extension is described in TRADEOFFS.md.

### Unit normalisation

Every record carries both the original value and the normalised value:

| Field | Example |
|-------|---------|
| `quantity_original` | `528.344` |
| `unit_original` | `GAL` |
| `conversion_factor` | `3.78541` (US gallons → litres) |
| `quantity` | `1999.99...` |
| `unit` | `L` |

This is not lossy. An auditor can reconstruct the original value, verify the conversion factor, and trace it back to the source row. The conversion factors are defined in the SAP parser's `UNIT_TO_LITRES` table with explicit source comments.

Units not in the lookup table pass through unchanged with `conversion_factor=1` and the record is flagged `SUSPICIOUS`. This is the correct behaviour — better to surface an unknown unit than to silently produce a wrong number.

### Source provenance

`source_id` stores the identifier that would allow you to find this record in the source system:
- SAP: the material document number (MBLNR)
- Utility: `{account}:{meter}:{bill_start}`
- Travel: the Concur report ID

This is different from the `raw_record` foreign key, which points to our internal representation. The `source_id` lets a client open their SAP system or Concur portal and find the original transaction.

### Period handling

`period_start` and `period_end` are the *normalised* activity period, after any pro-rating.

For utility data, billing periods that straddle calendar months are pro-rated by days (17 days of January out of 30-day billing period = 17/30 × kWh assigned to January). The billing period dates are preserved in `extra_data.billing_period_start` and `extra_data.billing_period_end`. An analyst can see both.

### extra_data

Source-specific fields that don't map to the standard schema go here. Examples:
- SAP: `material_number`, `movement_type`, `cost_center`, `order`
- Utility: `tariff`, `demand_kw`, `read_type`, `prorated_from_billing_period`
- Travel: `employee_id`, `from_city`, `to_city`, `cabin_class`

This is a deliberate design choice. I could have created separate models (`SAPRecord`, `UtilityRecord`, `TravelRecord`) with typed columns, but that would make the review dashboard harder to build generically. The tradeoff is that `extra_data` is untyped JSON — fine for display, bad for querying. If we ever need to query by `cabin_class = 'business'`, that field should be promoted to a typed column.

### Review workflow

```
PENDING ─► APPROVED (locked_for_audit=True, immutable)
         ─► REJECTED
         ─► FLAGGED ─► PENDING (reset) ─► APPROVED / REJECTED
```

Once `locked_for_audit=True`, no further edits are allowed. This is enforced at the serializer level (`EmissionRecordUpdateSerializer.update`) and at the review action level (`ReviewActionView.post`). Locking is irreversible in this prototype — a real system would need a supervisor unlock workflow.

### version field

An integer that increments on every change (edits and review actions). The `EmissionRecordEdit` table records `record_version` at the time of each change, so you can reconstruct the full history of any record at any version.

---

## EmissionRecordEdit

Append-only log of every field change. Never deleted, never updated.

| Field | Purpose |
|-------|---------|
| `field_name` | The field that changed |
| `old_value` | Text representation of the previous value |
| `new_value` | Text representation of the new value |
| `reason` | Required for edits (enforced in UI); optional for review actions |
| `record_version` | Version of the parent record at time of this edit |

Text representation is intentional: it survives schema changes. If `unit` changes from a free-text field to a FK to a `Unit` table in the future, the edit log still contains the readable string.

---

## What I didn't model (and why)

**EmissionFactor** — the CO₂e conversion factor per unit of activity. This is where the emissions calculation actually lives (litres of diesel × kg CO₂e per litre = tCO₂e). I didn't build it because:
1. Emission factor databases (DEFRA, EPA, IPCC) are versioned and geographically scoped. Using the wrong factor is a compliance risk, not just a data quality issue.
2. The assignment asked to ingest and normalise the *activity data*, not compute the emissions figure.
3. The review dashboard is for activity data quality; emissions calculation is a downstream step that happens after audit sign-off.

**Multi-register utility rows** — when a TOU meter produces two rows (On-Peak / Off-Peak) for one billing period, we currently parse each as a separate `EmissionRecord`. For Scope 2 reporting this is fine (you sum them). For market-based accounting with time-differentiated EACs, you'd need to track register-level breakdown. Scoped out.

**Scope 3 Category 1** (Purchased goods and services from SAP procurement) — SAP MM data contains both fuel withdrawals (movement types 201/261) and general procurement. We only handle consumption movement types. Extending to procurement would require material-to-category mapping and spend-based emission factors, which is a significant research effort.
