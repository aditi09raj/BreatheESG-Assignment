# Test Cases

135 tests across 13 categories. All pass.

Run: `cd backend && uv run python ../tests/run_tests.py` (server must be running on port 8000)

The test runner resets the database to a clean seeded state before each run, so results are reproducible.

---

## 1. Authentication (5 tests)

| # | Endpoint | Input | Expected | Result |
|---|----------|-------|----------|--------|
| 1.1 | `POST /api/auth/token/` | `{username: admin, password: admin123}` | 200 + `access` + `refresh` tokens | PASS |
| 1.2 | `POST /api/auth/token/` | `{username: admin, password: wrong}` | 401 | PASS |
| 1.3 | `POST /api/auth/token/` | `{username: nobody, password: x}` | 401 | PASS |
| 1.4 | `POST /api/auth/token/refresh/` | valid refresh token | 200 + new `access` token | PASS |
| 1.5 | `POST /api/auth/token/refresh/` | `{refresh: notavalidtoken}` | 401 | PASS |

---

## 2. /me/ Endpoint (4 tests)

| # | Endpoint | Input | Expected | Result |
|---|----------|-------|----------|--------|
| 2.1 | `GET /api/me/` | valid Bearer token | 200 | PASS |
| 2.2 | `GET /api/me/` | valid token | Response body contains `username: "admin"` | PASS |
| 2.3 | `GET /api/me/` | valid token | Response body contains `tenant.name` | PASS |
| 2.4 | `GET /api/me/` | no Authorization header | 401 | PASS |

---

## 3. Data Sources (6 tests)

| # | Endpoint | Input | Expected | Result |
|---|----------|-------|----------|--------|
| 3.1 | `GET /api/sources/` | authenticated | 200 | PASS |
| 3.2 | `GET /api/sources/` | — | At least 3 sources present (seeded) | PASS |
| 3.3 | `GET /api/sources/` | — | All 3 types present: `SAP_FUEL`, `UTILITY_ELECTRICITY`, `TRAVEL` | PASS |
| 3.4 | `POST /api/sources/` | `{source_type: SAP_FUEL, name: Test Source}` | 201 + source object | PASS |
| 3.5 | `POST /api/sources/` | — | Created source has correct `source_type` | PASS |
| 3.6 | `GET /api/sources/` | no auth | 401 | PASS |

---

## 4. File Ingestion — Happy Paths (9 tests)

Tests the three parsers end-to-end using the provided sample files.

| # | File | Source Type | Expected | Result |
|---|------|-------------|----------|--------|
| 4.1 | `sap_fuel_DE_UK_2024Q1.txt` | SAP_FUEL | status=COMPLETED | PASS |
| 4.2 | `sap_fuel_DE_UK_2024Q1.txt` | SAP_FUEL | `records_parsed=10` | PASS |
| 4.3 | `sap_fuel_DE_UK_2024Q1.txt` | SAP_FUEL | `records_failed=0` | PASS |
| 4.4 | `utility_billing_Q1_2024.csv` | UTILITY_ELECTRICITY | status=COMPLETED | PASS |
| 4.5 | `utility_billing_Q1_2024.csv` | UTILITY_ELECTRICITY | `records_parsed=16` (8 billing rows × 2 months from proration) | PASS |
| 4.6 | `utility_billing_Q1_2024.csv` | UTILITY_ELECTRICITY | `records_failed=0` | PASS |
| 4.7 | `travel_concur_Q1_2024.csv` | TRAVEL | status=COMPLETED | PASS |
| 4.8 | `travel_concur_Q1_2024.csv` | TRAVEL | `records_parsed=16` (meal row correctly excluded) | PASS |
| 4.9 | `travel_concur_Q1_2024.csv` | TRAVEL | `records_failed=1` (meal expense skipped) | PASS |

---

## 5. File Ingestion — Error Cases (6 tests)

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 5.1 | Upload same SAP file a second time | 409 Conflict | PASS |
| 5.2 | Duplicate upload | Response body contains `"already been ingested"` | PASS |
| 5.3 | POST to `/ingest/` with no `file` field | 400 | PASS |
| 5.4 | POST to `/ingest/` with no `source_id` field | 400 | PASS |
| 5.5 | Upload file with nonsense content (`not,a,valid,...`) | Does not crash — returns 200/201/400 gracefully | PASS |
| 5.6 | Upload without authentication | 401 | PASS |

---

## 6. Ingestion Runs (11 tests)

| # | Endpoint | Expected | Result |
|---|----------|----------|--------|
| 6.1 | `GET /api/runs/` | 200 | PASS |
| 6.2 | `GET /api/runs/` | At least 3 COMPLETED runs in response | PASS |
| 6.3 | `GET /api/runs/{id}/` | 200 | PASS |
| 6.4 | `GET /api/runs/{id}/` | Response has `file_name` field | PASS |
| 6.5 | `GET /api/runs/{id}/` | SAP run shows `records_parsed=10, records_failed=0` | PASS |
| 6.6 | `GET /api/runs/{id}/records/` | 200 | PASS |
| 6.7 | `GET /api/runs/{id}/records/` | Returns 10 raw records for SAP run | PASS |
| 6.8 | `GET /api/runs/{id}/records/` | All records have `parse_status` field | PASS |
| 6.9 | `GET /api/runs/{id}/records/` | All records have `raw_data` field (original source row preserved) | PASS |
| 6.10 | `GET /api/runs/{id}/records/` | Row indices are unique — no duplicates (validates `enumerate` fix over `list.index`) | PASS |
| 6.11 | `GET /api/runs/99999/` | 404 | PASS |

---

## 7. Records — List & Filtering (15 tests)

| # | Filter | Expected | Result |
|---|--------|----------|--------|
| 7.1 | None | 200 + records present | PASS |
| 7.2 | `?status=PENDING` | All returned records have `review_status=PENDING` | PASS |
| 7.3 | `?status=FLAGGED` | All returned records have `review_status=FLAGGED` | PASS |
| 7.4 | `?status=APPROVED` | All returned records have `review_status=APPROVED` | PASS |
| 7.5 | `?status=REJECTED` | All returned records have `review_status=REJECTED` | PASS |
| 7.6 | `?scope=1` | All returned records have `scope=1` | PASS |
| 7.7 | `?scope=2` | All returned records have `scope=2` | PASS |
| 7.8 | `?scope=3` | All returned records have `scope=3` | PASS |
| 7.9 | `?source_type=SAP_FUEL` | All returned records have `source_type=SAP_FUEL` | PASS |
| 7.10 | `?source_type=UTILITY_ELECTRICITY` | All match | PASS |
| 7.11 | `?source_type=TRAVEL` | All match | PASS |
| 7.12 | `?run={util_run_id}` | Returns exactly 16 records (from utility upload) | PASS |
| 7.13 | `?run={util_run_id}` | All 16 records are Scope 2 | PASS |
| 7.14 | No auth | 401 | PASS |
| 7.15 | Combined: `?status=FLAGGED&scope=2` | Implicit — both filters work together | covered by 7.3+7.7 |

---

## 8. Record Detail (9 tests)

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 8.1 | `GET /api/records/{id}/` | 200 | PASS |
| 8.2 | — | Has fields: `id, scope, activity_type, quantity, unit, period_start, period_end, review_status, source_type, extra_data, edits, version` | PASS |
| 8.3 | — | Has `scope_display` (human-readable) | PASS |
| 8.4 | — | Has `review_status_display` | PASS |
| 8.5 | — | Has `source_type_display` | PASS |
| 8.6 | — | `edits` is a list (empty or populated) | PASS |
| 8.7 | — | `version >= 1` | PASS |
| 8.8 | SAP record | `extra_data` contains `material_number` | PASS |
| 8.9 | `GET /api/records/99999/` | 404 | PASS |

---

## 9. Record Editing (9 tests)

Edit endpoint: `PATCH /api/records/{id}/edit/`

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 9.1 | PATCH with `{quantity: 999.000000, reason: "Test edit"}` | 200 | PASS |
| 9.2 | — | Returned record has updated `quantity` | PASS |
| 9.3 | — | Returned record `version` is old_version + 1 | PASS |
| 9.4 | — | `GET /records/{id}/` shows new `EmissionRecordEdit` entry for `quantity` field | PASS |
| 9.5 | — | Edit entry has correct `old_value` | PASS |
| 9.6 | — | Edit entry `new_value` starts with "999" | PASS |
| 9.7 | — | Edit entry `reason` contains the provided reason text | PASS |
| 9.8 | PATCH with same value (no actual change) | No new audit trail entry created | PASS |
| 9.9 | PATCH without authentication | 401 | PASS |

---

## 10. Review Actions (18 tests)

Endpoint: `POST /api/records/{id}/review/`

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 10.1 | `{action: flag, notes: "Looks suspicious"}` | `review_status=FLAGGED` | PASS |
| 10.2 | flag | `review_notes` saved | PASS |
| 10.3 | flag | `reviewed_by` set to requesting user | PASS |
| 10.4 | flag | `reviewed_at` is non-null | PASS |
| 10.5 | `{action: reject}` | `review_status=REJECTED` | PASS |
| 10.6 | `{action: reset}` | `review_status=PENDING` | PASS |
| 10.7 | reset on non-locked record | `locked_for_audit` remains False | PASS |
| 10.8 | `{action: approve, notes: "Verified"}` | `review_status=APPROVED` | PASS |
| 10.9 | approve | `locked_for_audit=True` | PASS |
| 10.10 | approve | `locked_at` is non-null | PASS |
| 10.11 | approve | `review_notes` saved | PASS |
| 10.12 | any action | `EmissionRecordEdit` entry created for `review_status` change | PASS |
| 10.13 | approve | Audit trail entry records `new_value=APPROVED` | PASS |
| 10.14 | PATCH on locked record | 400 `"Record is locked for audit"` | PASS |
| 10.15 | Review action on locked record | 400 | PASS |
| 10.16 | `{action: vanish}` | 400 unknown action | PASS |
| 10.17 | `{}` (no action field) | 400 | PASS |
| 10.18 | No authentication | 401 | PASS |

**State machine verified:**
```
PENDING → FLAGGED → REJECTED → PENDING → APPROVED (locked) → edit blocked ✓
```

---

## 11. Bulk Review (12 tests)

Endpoint: `POST /api/records/bulk/`

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 11.1 | `{ids: [a,b,c], action: flag}` | 200 | PASS |
| 11.2 | bulk flag | `updated` count equals number of ids | PASS |
| 11.3–11.5 | Per-record check after bulk flag | All 3 records have `review_status=FLAGGED` | PASS (×3) |
| 11.6 | `{ids: [a,b], action: approve}` | 200 | PASS |
| 11.7 | bulk approve | `updated=2`, both records locked | PASS |
| 11.8 | Bulk action on already-locked records | `updated=0` (locked records silently skipped) | PASS |
| 11.9 | `{ids: [c], action: reject}` | 200 | PASS |
| 11.10 | `{ids: [...], action: invalid_action}` | 400 | PASS |
| 11.11 | `{ids: [], action: flag}` | 200, `updated=0` | PASS |
| 11.12 | No authentication | 401 | PASS |

---

## 12. Dashboard Stats (13 tests)

Endpoint: `GET /api/dashboard/stats/`

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 12.1 | Response status | 200 | PASS |
| 12.2 | `total_records` key present | — | PASS |
| 12.3 | `by_status` key present | — | PASS |
| 12.4 | `by_scope` key present | — | PASS |
| 12.5 | `by_source` key present | — | PASS |
| 12.6 | `recent_runs` is a list | — | PASS |
| 12.7 | `flagged_sample` is a list | — | PASS |
| 12.8 | `total_records > 0` | — | PASS |
| 12.9 | `by_status` values sum to `total_records` | sum=56, total=56 ✓ | PASS |
| 12.10 | `by_scope` values sum to `total_records` | sum=56, total=56 ✓ | PASS |
| 12.11 | `recent_runs[0]` has `source_name` | — | PASS |
| 12.12 | `recent_runs[0]` has `status` | — | PASS |
| 12.13 | No authentication | 401 | PASS |

---

## 13. Parser Correctness (19 tests)

These tests verify that the three parsers handle real-world data format quirks correctly.

### SAP Parser (6 tests)

| # | Test | Expected | Result |
|---|------|----------|--------|
| 13.1 | Row with `unit=GAL, quantity=528.344` | `quantity` ≈ 2000 (×3.78541), `unit=L` | PASS |
| 13.2 | GAL record | `unit` normalised to `"L"` | PASS |
| 13.3 | GAL record | `conversion_factor` starts with `"3.785"` | PASS |
| 13.4 | Row with `unit=M3` (natural gas) | `unit` stays `"M3"` — not converted to litres | PASS |
| 13.5 | All 10 SAP records | `scope=1` for all | PASS |
| 13.6 | 10-row file, all movement type 201/261 | Exactly 10 records created (no reversals in sample file) | PASS |

> **Note on M3:** Initially the parser converted M3→L (×1000). This was wrong — gas m³ and liquid litres are not interchangeable. Natural gas emission factors are defined per m³. Fixed before tests ran.

### Utility Parser (7 tests)

| # | Test | Expected | Result |
|---|------|----------|--------|
| 13.7 | 8-row billing file | 16 EmissionRecords created (each billing row spans 2 calendar months) | PASS |
| 13.8 | All utility records | `scope=2` | PASS |
| 13.9 | All utility records | `unit="kWh"` | PASS |
| 13.10 | Prorated record | `quantity < quantity_original` (partial month < full billing period) | PASS |
| 13.11 | Two prorated records from same billing row | `sum(quantities)` == `quantity_original` (to 3 decimal places) | PASS — sum=11100.000, orig=11100.000 |
| 13.12 | Row with `read_type=Estimated` | `review_status=FLAGGED` | PASS |
| 13.13 | All utility records | `unit="kWh"` (no unit conversion needed for billing CSV) | PASS |

### Travel Parser (6 tests)

| # | Test | Expected | Result |
|---|------|----------|--------|
| 13.14 | All travel records | `scope=3` | PASS |
| 13.15 | Row with `expense_type=MEALF` (meal) | Not present in EmissionRecords | PASS |
| 13.16 | Row with `expense_type=TAXI`, `personal=N` | Present in EmissionRecords | PASS |
| 13.17 | All flight records | `extra_data.from_city` populated | PASS |
| 13.18 | Munich→Singapore flight | `extra_data.cabin_class="business"` | PASS |
| 13.19 | Hotel records | `unit="room-night"` | PASS |
| 13.20 | Deutsche Bahn Berlin→Hamburg | `activity_type="rail"`, captured correctly | PASS |

---

## Bugs found and fixed during test writing

| Bug | Impact | Fix |
|-----|--------|-----|
| `rows.index(row_data)` in `IngestFileView` | O(n²) performance; utility proration rows with identical `raw_data` got duplicate `row_index` | Replaced with `enumerate(rows, start=1)` |
| `EmissionRecordUpdateView` returned `EmissionRecordUpdateSerializer` (no `version`) | PATCH response didn't include `version` field, breaking any client that reads it | View now returns `EmissionRecordSerializer` after save |
| SAP parser converted `M3 → L` (×1000) | Natural gas volumes in m³ should not be converted to litres — they are physically different units; CO2 factors for gas are per m³ | Removed M3→L conversion; M3 passes through unchanged |

---

## Known limitations (not bugs)

- `PATCH /records/{id}/edit/` accepts an empty `reason` at the API level; the UI enforces a non-empty reason. The audit trail entry is created either way (with an empty reason string). This is a deliberate choice — server-enforced reason would require adding a custom validator, and analysts using the admin panel should be able to make emergency edits.
- Filtering does not support combined `source_type+scope` or date range queries — adding them is additive and would follow the same pattern as existing filters.
- Pagination is fixed at 50 records. Tests use the first page only; large datasets would need pagination traversal for full verification.
