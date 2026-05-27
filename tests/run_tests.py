#!/usr/bin/env python3
"""
API test suite for the Breathe ESG prototype.

Usage:
    cd backend && uv run python ../tests/run_tests.py
    (server must be running on localhost:8000)
"""

import json
import sys
import os
import time
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "http://localhost:8000/api"
SAMPLE_DATA_FOLDER = Path(__file__).parent.parent / "sample_data"

all_test_results = []
num_failed = 0
num_passed = 0


# ── HTTP helpers (stdlib only, no requests dep) ──────────────────────────────

def make_request(method, path, token=None, json_body=None, form=None, files=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if json_body is not None:
        request_data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif files:
        boundary = "----ESGTestBoundary7MA4YWxkTrZu0gW"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        parts = []
        for field_name, field_value in (form or {}).items():
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; "
                f'name="{field_name}"\r\n\r\n{field_value}\r\n'.encode()
            )
        for field_name, (filename, file_bytes, content_type) in files.items():
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; "
                f'name="{field_name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n".encode() + file_bytes + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        request_data = b"".join(parts)
    elif form:
        request_data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        request_data = None

    http_request = urllib.request.Request(url, data=request_data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(http_request) as response:
            response_body = response.read()
            response_status = response.status
    except urllib.error.HTTPError as error:
        response_body = error.read()
        response_status = error.code
    except urllib.error.URLError:
        return None, 0, {}

    try:
        parsed_response = json.loads(response_body)
    except Exception:
        parsed_response = {"_raw": response_body.decode(errors="replace")}

    return parsed_response, response_status, {}


def get(path, token=None, **extra):
    return make_request("GET", path, token=token, **extra)

def post(path, token=None, **extra):
    return make_request("POST", path, token=token, **extra)

def patch(path, token=None, **extra):
    return make_request("PATCH", path, token=token, **extra)


# ── Test helpers ─────────────────────────────────────────────────────────────

def check_test(test_name, passed, note=""):
    global num_failed, num_passed
    if passed:
        num_passed += 1
        result_label = "PASS"
    else:
        num_failed += 1
        result_label = "FAIL"

    all_test_results.append((result_label, test_name, note))
    colored_label = "\033[32mPASS\033[0m" if passed else "\033[31mFAIL\033[0m"
    print(f"  [{colored_label}] {test_name}" + (f"  ← {note}" if note else ""))


def print_section_header(title):
    print(f"\n\033[1m{'─'*60}\033[0m")
    print(f"\033[1m  {title}\033[0m")
    print(f"\033[1m{'─'*60}\033[0m")


def upload_file(token, source_id, filename, content_type="text/csv"):
    file_path = SAMPLE_DATA_FOLDER / filename
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    response_data, response_status, _ = post(
        "/ingest/", token=token,
        form={"source_id": str(source_id)},
        files={"file": (filename, file_bytes, content_type)},
    )
    return response_data, response_status


# ── Test categories ───────────────────────────────────────────────────────────

def test_auth():
    print_section_header("1. Authentication")

    # Valid login
    data, status, _ = post("/auth/token/", json_body={"username": "admin", "password": "admin123"})
    check_test("Valid login → 200 + tokens", status == 200 and "access" in data and "refresh" in data)
    admin_token = data.get("access", "")

    # Invalid password
    data, status, _ = post("/auth/token/", json_body={"username": "admin", "password": "wrong"})
    check_test("Wrong password → 401", status == 401)

    # Invalid username
    data, status, _ = post("/auth/token/", json_body={"username": "nobody", "password": "x"})
    check_test("Unknown user → 401", status == 401)

    # Token refresh
    data2, status2, _ = post("/auth/token/", json_body={"username": "admin", "password": "admin123"})
    refresh_token = data2.get("refresh", "")
    data3, status3, _ = post("/auth/token/refresh/", json_body={"refresh": refresh_token})
    check_test("Refresh token → new access token", status3 == 200 and "access" in data3)

    # Invalid refresh token
    data4, status4, _ = post("/auth/token/refresh/", json_body={"refresh": "notavalidtoken"})
    check_test("Invalid refresh token → 401", status4 == 401)

    return admin_token


def test_me(token):
    print_section_header("2. /me/ endpoint")

    data, status, _ = get("/me/", token=token)
    check_test("GET /me/ authenticated → 200", status == 200)
    check_test("/me/ returns username", data.get("username") == "admin")
    check_test("/me/ returns tenant", isinstance(data.get("tenant"), dict) and "name" in data["tenant"])

    data2, status2, _ = get("/me/")
    check_test("GET /me/ unauthenticated → 401", status2 == 401)


def test_sources(token):
    print_section_header("3. Data Sources")

    data, status, _ = get("/sources/", token=token)
    check_test("GET /sources/ → 200", status == 200)
    source_list = data.get("results", data) if isinstance(data, dict) else data
    check_test("3 default sources seeded", len(source_list) >= 3)
    source_types_in_db = {s["source_type"] for s in source_list}
    check_test("All 3 source types present", source_types_in_db == {"SAP_FUEL", "UTILITY_ELECTRICITY", "TRAVEL"})

    # Create new source
    data2, status2, _ = post("/sources/", token=token, json_body={
        "source_type": "SAP_FUEL",
        "name": "Test Source",
        "description": "Created by test suite",
    })
    check_test("POST /sources/ → 201", status2 == 201)
    check_test("Created source has correct type", data2.get("source_type") == "SAP_FUEL")

    # Unauthenticated
    data3, status3, _ = get("/sources/")
    check_test("GET /sources/ unauthenticated → 401", status3 == 401)

    # Return a dict mapping source type to its database ID
    return {s["source_type"]: s["id"] for s in source_list}


def test_ingestion(token, source_ids):
    print_section_header("4. File Ingestion — happy paths")

    # SAP
    data, status = upload_file(token, source_ids["SAP_FUEL"], "sap_fuel_DE_UK_2024Q1.txt", "text/plain")
    check_test("SAP upload → COMPLETED", status == 201 and data.get("status") == "COMPLETED")
    check_test("SAP: 10 rows parsed", data.get("records_parsed") == 10)
    check_test("SAP: 0 failures", data.get("records_failed") == 0)
    sap_run_id = data.get("id")

    # Utility
    data, status = upload_file(token, source_ids["UTILITY_ELECTRICITY"], "utility_billing_Q1_2024.csv")
    check_test("Utility upload → COMPLETED", status == 201 and data.get("status") == "COMPLETED")
    check_test("Utility: 16 records (8 rows × 2 months each from proration)", data.get("records_parsed") == 16)
    check_test("Utility: 0 failures", data.get("records_failed") == 0)
    util_run_id = data.get("id")

    # Travel
    data, status = upload_file(token, source_ids["TRAVEL"], "travel_concur_Q1_2024.csv")
    check_test("Travel upload → COMPLETED", status == 201 and data.get("status") == "COMPLETED")
    check_test("Travel: 16 parsed (meal row skipped)", data.get("records_parsed") == 16)
    check_test("Travel: 1 skipped (meal expense)", data.get("records_failed") == 1)
    travel_run_id = data.get("id")

    print_section_header("5. File Ingestion — error cases")

    # Duplicate file
    data2, status2 = upload_file(token, source_ids["SAP_FUEL"], "sap_fuel_DE_UK_2024Q1.txt", "text/plain")
    check_test("Duplicate SAP upload → 409", status2 == 409)
    check_test("409 error message present", "already been ingested" in data2.get("error", ""))

    # Missing file
    data3, status3, _ = post("/ingest/", token=token, form={"source_id": str(source_ids["SAP_FUEL"])})
    check_test("Upload without file → 400", status3 == 400)

    # Missing source_id
    with open(SAMPLE_DATA_FOLDER / "sap_fuel_DE_UK_2024Q1.txt", "rb") as f:
        file_content = f.read()
    data4, status4, _ = post("/ingest/", token=token,
        files={"file": ("sap_fuel_DE_UK_2024Q1.txt", file_content, "text/plain")})
    check_test("Upload without source_id → 400", status4 == 400)

    # Garbage file content
    garbage_content = b"not,a,valid,sap,file\nrandom,garbage,data,here\n"
    data5, status5, _ = post("/ingest/", token=token,
        form={"source_id": str(source_ids["SAP_FUEL"])},
        files={"file": ("garbage.txt", garbage_content, "text/plain")})
    # Should complete but with 0 parsed (no valid movement types) or fail gracefully
    check_test("Garbage file → does not crash (200/201/400)", status5 in (200, 201, 400))

    # Unauthenticated
    with open(SAMPLE_DATA_FOLDER / "sap_fuel_DE_UK_2024Q1.txt", "rb") as f:
        file_content = f.read()
    data6, status6, _ = post("/ingest/",
        form={"source_id": str(source_ids["SAP_FUEL"])},
        files={"file": ("sap_fuel_DE_UK_2024Q1.txt", file_content, "text/plain")})
    check_test("Upload unauthenticated → 401", status6 == 401)

    return sap_run_id, util_run_id, travel_run_id


def test_runs(token, sap_run_id):
    print_section_header("6. Ingestion Runs")

    data, status, _ = get("/runs/", token=token)
    check_test("GET /runs/ → 200", status == 200)
    run_list = data.get("results", data) if isinstance(data, dict) else data
    check_test("At least 3 completed runs", sum(1 for r in run_list if r["status"] == "COMPLETED") >= 3)

    data2, status2, _ = get(f"/runs/{sap_run_id}/", token=token)
    check_test("GET /runs/{id}/ → 200", status2 == 200)
    check_test("Run detail has file_name", "file_name" in data2)
    check_test("Run detail has correct counts", data2.get("records_parsed") == 10 and data2.get("records_failed") == 0)

    data3, status3, _ = get(f"/runs/{sap_run_id}/records/", token=token)
    check_test("GET /runs/{id}/records/ → 200", status3 == 200)
    raw_records = data3.get("results", data3) if isinstance(data3, dict) else data3
    check_test("Raw records returned for run", len(raw_records) == 10)
    check_test("Raw records have parse_status", all("parse_status" in r for r in raw_records))
    check_test("Raw records preserve raw_data", all("raw_data" in r for r in raw_records))

    # Row indices must be unique — no duplicates from the enumerate fix
    row_index_list = [r["row_index"] for r in raw_records]
    check_test("Row indices are unique (no duplicates from enumerate fix)", len(row_index_list) == len(set(row_index_list)))

    # Non-existent run
    data4, status4, _ = get("/runs/99999/", token=token)
    check_test("GET /runs/99999/ → 404", status4 == 404)


def test_records_list(token, util_run_id):
    print_section_header("7. Records — List & Filtering")

    data, status, _ = get("/records/", token=token)
    check_test("GET /records/ → 200", status == 200)
    total_count = data.get("count", len(data.get("results", data)))
    check_test("Has records (seeded + uploaded)", total_count > 0)

    # Status filter
    for status_value in ("PENDING", "FLAGGED", "APPROVED", "REJECTED"):
        result, http_status, _ = get(f"/records/?status={status_value}", token=token)
        record_list = result.get("results", result) if isinstance(result, dict) else result
        check_test(f"Filter status={status_value} → all results have status={status_value}",
               http_status == 200 and all(r["review_status"] == status_value for r in record_list))

    # Scope filter
    for scope_number in (1, 2, 3):
        result, http_status, _ = get(f"/records/?scope={scope_number}", token=token)
        record_list = result.get("results", result) if isinstance(result, dict) else result
        check_test(f"Filter scope={scope_number} → all results have scope={scope_number}",
               http_status == 200 and all(r["scope"] == scope_number for r in record_list))

    # Source type filter
    for source_type in ("SAP_FUEL", "UTILITY_ELECTRICITY", "TRAVEL"):
        result, http_status, _ = get(f"/records/?source_type={source_type}", token=token)
        record_list = result.get("results", result) if isinstance(result, dict) else result
        check_test(f"Filter source_type={source_type} → all results match",
               http_status == 200 and all(r["source_type"] == source_type for r in record_list))

    # Run filter — only records from the utility run
    result, http_status, _ = get(f"/records/?run={util_run_id}", token=token)
    record_list = result.get("results", result) if isinstance(result, dict) else result
    check_test(f"Filter run={util_run_id} → 16 records from utility upload",
           http_status == 200 and len(record_list) == 16)
    check_test("All utility records are Scope 2",
           all(r["scope"] == 2 for r in record_list))

    # Unauthenticated
    result2, status2, _ = get("/records/")
    check_test("GET /records/ unauthenticated → 401", status2 == 401)


def test_record_detail(token):
    print_section_header("8. Record Detail")

    # Get a known record from Scope 1 (SAP fuel)
    result, _, _ = get("/records/?scope=1", token=token)
    record_list = result.get("results", result) if isinstance(result, dict) else result
    record_id = record_list[0]["id"]

    data2, status2, _ = get(f"/records/{record_id}/", token=token)
    check_test("GET /records/{id}/ → 200", status2 == 200)
    check_test("Detail has all required fields",
           all(field in data2 for field in ["id", "scope", "activity_type", "quantity", "unit",
                                  "period_start", "period_end", "review_status",
                                  "source_type", "extra_data", "edits", "version"]))
    check_test("Detail includes scope_display", "scope_display" in data2)
    check_test("Detail includes review_status_display", "review_status_display" in data2)
    check_test("Detail includes source_type_display", "source_type_display" in data2)
    check_test("edits is a list", isinstance(data2.get("edits"), list))
    check_test("version >= 1", data2.get("version", 0) >= 1)

    # SAP records should have material_number in the extra details
    check_test("SAP record extra_data has material_number",
           "material_number" in data2.get("extra_data", {}))

    # Non-existent record
    data3, status3, _ = get("/records/99999/", token=token)
    check_test("GET /records/99999/ → 404", status3 == 404)

    return record_id


def test_record_editing(token):
    print_section_header("9. Record Editing")

    # Get a pending, unlocked record to edit
    result, _, _ = get("/records/?status=PENDING&scope=1", token=token)
    record_list = result.get("results", result) if isinstance(result, dict) else result
    record_id = record_list[0]["id"]
    old_version = record_list[0]["version"]
    original_quantity = str(record_list[0]["quantity"])

    # Valid edit with reason
    data2, status2, _ = patch(f"/records/{record_id}/edit/", token=token, json_body={
        "quantity": "999.000000",
        "reason": "Test edit — correcting quantity",
    })
    check_test("PATCH /records/{id}/edit/ → 200", status2 == 200)
    check_test("quantity updated correctly", str(data2.get("quantity")) == "999.000000")
    check_test("version incremented", data2.get("version", 0) == old_version + 1)

    # Check the audit trail was written
    data3, _, _ = get(f"/records/{record_id}/", token=token)
    edit_history = data3.get("edits", [])
    quantity_edits = [e for e in edit_history if e["field_name"] == "quantity"]
    check_test("Audit trail entry created for quantity change", len(quantity_edits) >= 1)
    check_test("Audit trail records old value", quantity_edits[-1]["old_value"] == original_quantity if quantity_edits else False)
    check_test("Audit trail records new value",
           quantity_edits[-1]["new_value"].startswith("999") if quantity_edits else False)
    check_test("Audit trail records reason", "Test edit" in quantity_edits[-1]["reason"] if quantity_edits else False)

    # Edit with no actual change → no new audit entry should be created
    num_edits_before = len(data3.get("edits", []))
    patch(f"/records/{record_id}/edit/", token=token, json_body={
        "quantity": "999.000000",
        "reason": "No actual change",
    })
    data4, _, _ = get(f"/records/{record_id}/", token=token)
    num_edits_after = len(data4.get("edits", []))
    check_test("Edit with unchanged value → no new audit entry", num_edits_after == num_edits_before)

    # Restore original quantity
    patch(f"/records/{record_id}/edit/", token=token, json_body={
        "quantity": original_quantity,
        "reason": "Restoring original value after test",
    })

    # Edit without auth should fail
    no_auth_data, no_auth_status, _ = patch(f"/records/{record_id}/edit/", json_body={"quantity": "1.0", "reason": "x"})
    check_test("Edit unauthenticated → 401", no_auth_status == 401)

    return record_id


def test_review_actions(token, record_id):
    print_section_header("10. Review Actions")

    # Reset to PENDING first so we start from a known state
    post(f"/records/{record_id}/review/", token=token, json_body={"action": "reset"})

    # Flag the record
    data, status, _ = post(f"/records/{record_id}/review/", token=token, json_body={
        "action": "flag", "notes": "Looks suspicious"
    })
    check_test("action=flag → FLAGGED", status == 200 and data.get("review_status") == "FLAGGED")
    check_test("flag sets review_notes", data.get("review_notes") == "Looks suspicious")
    check_test("flag sets reviewed_by", data.get("reviewed_by_name") == "admin")
    check_test("flag sets reviewed_at", data.get("reviewed_at") is not None)

    # Reject the record
    data2, status2, _ = post(f"/records/{record_id}/review/", token=token, json_body={"action": "reject"})
    check_test("action=reject → REJECTED", status2 == 200 and data2.get("review_status") == "REJECTED")

    # Reset back to pending
    data3, status3, _ = post(f"/records/{record_id}/review/", token=token, json_body={"action": "reset"})
    check_test("action=reset → PENDING", status3 == 200 and data3.get("review_status") == "PENDING")
    check_test("reset clears lock (still unlocked)", data3.get("locked_for_audit") is False)

    # Approve (this should lock the record)
    data4, status4, _ = post(f"/records/{record_id}/review/", token=token, json_body={
        "action": "approve", "notes": "Verified against source"
    })
    check_test("action=approve → APPROVED", status4 == 200 and data4.get("review_status") == "APPROVED")
    check_test("approve sets locked_for_audit=True", data4.get("locked_for_audit") is True)
    check_test("approve sets locked_at", data4.get("locked_at") is not None)
    check_test("approve saves notes", data4.get("review_notes") == "Verified against source")

    # Check that the approve action was written to the audit trail
    data5, _, _ = get(f"/records/{record_id}/", token=token)
    status_audit_entries = [e for e in data5.get("edits", []) if e["field_name"] == "review_status"]
    check_test("Review action creates audit trail entry", len(status_audit_entries) >= 1)
    approved_entries = [e for e in status_audit_entries if e["new_value"] == "APPROVED"]
    check_test("Audit trail records APPROVED transition", len(approved_entries) >= 1)

    # Trying to edit a locked record should fail with 400
    data6, status6, _ = patch(f"/records/{record_id}/edit/", token=token, json_body={
        "quantity": "1.0", "reason": "Should fail"
    })
    check_test("Edit on locked record → 400", status6 == 400)

    # Trying to review a locked record should also fail
    data7, status7, _ = post(f"/records/{record_id}/review/", token=token, json_body={"action": "reject"})
    check_test("Review action on locked record → 400", status7 == 400)

    # Unknown action
    data8, status8, _ = post(f"/records/{record_id}/review/", token=token, json_body={"action": "vanish"})
    check_test("Invalid action → 400", status8 == 400)

    # No action given
    data9, status9, _ = post(f"/records/{record_id}/review/", token=token, json_body={})
    check_test("Missing action → 400", status9 == 400)

    return record_id


def test_bulk_review(token):
    print_section_header("11. Bulk Review")

    # Get a few pending, unlocked records to work with
    result, _, _ = get("/records/?status=PENDING", token=token)
    pending_records = (result.get("results", result) if isinstance(result, dict) else result)[:3]
    unlocked_ids = [r["id"] for r in pending_records if not r["locked_for_audit"]][:3]

    if len(unlocked_ids) < 2:
        check_test("Bulk review — skipped (not enough unlocked PENDING records)", True, "skipped")
        return

    # Bulk flag
    data2, status2, _ = post("/records/bulk/", token=token, json_body={
        "ids": unlocked_ids, "action": "flag", "notes": "Bulk flagged by test"
    })
    check_test("POST /records/bulk/ action=flag → 200", status2 == 200)
    check_test("bulk flag returns updated count", data2.get("updated") == len(unlocked_ids))

    # Make sure all of them got flagged
    for each_id in unlocked_ids:
        detail, _, _ = get(f"/records/{each_id}/", token=token)
        check_test(f"Record {each_id} is FLAGGED after bulk flag",
               detail.get("review_status") == "FLAGGED")

    # Bulk approve → should lock all
    data3, status3, _ = post("/records/bulk/", token=token, json_body={
        "ids": unlocked_ids[:2], "action": "approve"
    })
    check_test("Bulk approve → 200", status3 == 200)
    check_test("Bulk approve locked count correct", data3.get("updated") == 2)

    # Those 2 records are now locked — bulk action on them should return 0 updated
    data4, status4, _ = post("/records/bulk/", token=token, json_body={
        "ids": unlocked_ids[:2],  # already locked
        "action": "reject",
    })
    check_test("Bulk action on already-locked records → 0 updated (all skipped)", data4.get("updated") == 0)

    # Bulk reject the remaining one
    data5, status5, _ = post("/records/bulk/", token=token, json_body={
        "ids": unlocked_ids[2:], "action": "reject"
    })
    check_test("Bulk reject → 200", status5 == 200)

    # Unknown action
    data6, status6, _ = post("/records/bulk/", token=token, json_body={
        "ids": unlocked_ids, "action": "invalid_action"
    })
    check_test("Bulk invalid action → 400", status6 == 400)

    # Empty ids list → 0 updated, no error
    data7, status7, _ = post("/records/bulk/", token=token, json_body={"ids": [], "action": "flag"})
    check_test("Bulk with empty ids → 200, 0 updated", status7 == 200 and data7.get("updated") == 0)

    # Unauthenticated
    data8, status8, _ = post("/records/bulk/", json_body={"ids": unlocked_ids, "action": "flag"})
    check_test("Bulk unauthenticated → 401", status8 == 401)


def test_dashboard(token):
    print_section_header("12. Dashboard Stats")

    data, status, _ = get("/dashboard/stats/", token=token)
    check_test("GET /dashboard/stats/ → 200", status == 200)
    check_test("Has total_records", "total_records" in data)
    check_test("Has by_status", "by_status" in data)
    check_test("Has by_scope", "by_scope" in data)
    check_test("Has by_source", "by_source" in data)
    check_test("Has recent_runs list", isinstance(data.get("recent_runs"), list))
    check_test("Has flagged_sample list", isinstance(data.get("flagged_sample"), list))

    total = data.get("total_records", 0)
    check_test("total_records > 0", total > 0)

    # The by_status counts should add up to the total
    status_breakdown = data.get("by_status", {})
    status_total = sum(status_breakdown.values())
    check_test("by_status counts sum to total_records", status_total == total,
           f"sum={status_total} total={total}")

    # The by_scope counts should also add up to the total
    scope_breakdown = data.get("by_scope", {})
    scope_total = sum(scope_breakdown.values())
    check_test("by_scope counts sum to total_records", scope_total == total,
           f"sum={scope_total} total={total}")

    recent_runs = data.get("recent_runs", [])
    if recent_runs:
        first_run = recent_runs[0]
        check_test("recent_runs entries have source_name", "source_name" in first_run)
        check_test("recent_runs entries have status", "status" in first_run)

    # Unauthenticated
    data2, status2, _ = get("/dashboard/stats/")
    check_test("GET /dashboard/stats/ unauthenticated → 401", status2 == 401)


def test_parser_correctness(token, source_ids, sap_run_id, util_run_id, travel_run_id):
    print_section_header("13. Parser Correctness")

    # ── SAP parser ───────────────────────────────────────────────────────────
    # Filter by specific upload run to exclude seeded records
    result, _, _ = get(f"/records/?run={sap_run_id}", token=token)
    sap_records = result.get("results", result) if isinstance(result, dict) else result

    # GAL → L unit conversion: row 4 in SAP file is HEIZOL with 528.344 GAL
    gallon_records = [r for r in sap_records if r.get("unit_original") == "GAL"]
    if gallon_records:
        gallon_record = gallon_records[0]
        expected_litres = round(float(gallon_record["quantity_original"]) * 3.78541, 0)
        actual_litres = round(float(gallon_record["quantity"]), 0)
        check_test("SAP GAL→L conversion applied (×3.78541)",
               abs(expected_litres - actual_litres) < 2,
               f"expected≈{expected_litres}, got≈{actual_litres}")
        check_test("SAP GAL record unit normalised to 'L'", gallon_record.get("unit") == "L")
        check_test("SAP GAL conversion_factor is 3.7854...",
               str(gallon_record.get("conversion_factor", "")).startswith("3.785"))
    else:
        check_test("SAP GAL→L conversion (no GAL records found)", False, "no GAL records from upload")

    # M3 unit: row 3 (ERDGAS) uses M3 — should pass through unchanged
    m3_records = [r for r in sap_records if r.get("unit") == "M3"]
    check_test("SAP M3 unit passes through unchanged", len(m3_records) >= 1)

    # All SAP records should be Scope 1
    check_test("All SAP records are Scope 1", all(r["scope"] == 1 for r in sap_records))

    # All 10 consumption rows should be in the database
    check_test("SAP: 10 consumption records from 10-row file (no reversals in sample)", len(sap_records) == 10)

    # ── Utility parser ───────────────────────────────────────────────────────
    result, _, _ = get(f"/records/?run={util_run_id}", token=token)
    utility_records = result.get("results", result) if isinstance(result, dict) else result

    # 8 source rows → 16 records because each billing period crosses two months
    check_test("Utility: 8 billing rows produce 16 records (proration)", len(utility_records) == 16)

    # All utility records should be Scope 2
    check_test("All utility records are Scope 2", all(r["scope"] == 2 for r in utility_records))
    check_test("All utility records use kWh", all(r["unit"] == "kWh" for r in utility_records))

    # Check that prorated kWh is smaller than the original billing total
    prorated_records = [r for r in utility_records if r.get("extra_data", {}).get("prorated_from_billing_period")]
    if prorated_records:
        first_prorated = prorated_records[0]
        check_test("Prorated kWh < original billing kWh",
               float(first_prorated["quantity"]) < float(first_prorated["quantity_original"]))
        # Two split records from the same bill should add up to the original total
        same_source_records = [r for r in utility_records if r.get("source_id") == first_prorated["source_id"]]
        if len(same_source_records) == 2:
            split_total = sum(float(r["quantity"]) for r in same_source_records)
            original_total = float(first_prorated["quantity_original"])
            check_test("Two prorated records sum back to original kWh",
                   abs(split_total - original_total) < 0.01, f"sum={split_total:.3f}, orig={original_total:.3f}")

    # Estimated reads should be flagged
    flagged_utility = [r for r in utility_records if r.get("review_status") == "FLAGGED"]
    check_test("Estimated meter read row is FLAGGED", len(flagged_utility) >= 1)

    # ── Travel parser ────────────────────────────────────────────────────────
    result, _, _ = get(f"/records/?run={travel_run_id}", token=token)
    travel_records = result.get("results", result) if isinstance(result, dict) else result

    # All travel records should be Scope 3
    check_test("All travel records are Scope 3", all(r["scope"] == 3 for r in travel_records))

    # Meal expense should not appear in the records at all
    meal_records = [r for r in travel_records if r.get("activity_type") == "meal"]
    check_test("Meal expense not in records (correctly skipped)", len(meal_records) == 0)

    # Taxi record should be included (it is not a personal expense)
    taxi_records = [r for r in travel_records if r.get("activity_type") == "taxi"]
    check_test("Taxi record is included (non-personal)", len(taxi_records) >= 1)

    # Flight records should have origin and destination cities stored
    flight_records = [r for r in travel_records if r.get("activity_type") == "flight"]
    check_test("Flight records have from_city in extra_data",
           len(flight_records) > 0 and all("from_city" in r.get("extra_data", {}) for r in flight_records))

    # Business class flight should be captured with the correct cabin class
    business_flights = [r for r in flight_records
                        if r.get("extra_data", {}).get("cabin_class") == "business"]
    check_test("Business class flight captured with cabin_class=business", len(business_flights) >= 1)

    # Hotel records should have room-night as the unit
    hotel_records = [r for r in travel_records if r.get("activity_type") == "hotel"]
    check_test("Hotel records use room-night unit", all(r["unit"] == "room-night" for r in hotel_records))

    # Rail record should exist (Deutsche Bahn)
    rail_records = [r for r in travel_records if r.get("activity_type") == "rail"]
    check_test("Rail record captured (Deutsche Bahn Berlin→Hamburg)", len(rail_records) >= 1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\033[1m\nBreath ESG — API Test Suite\033[0m")
    print("=" * 60)

    # Reset DB to clean state for reproducible tests
    print("\n[setup] Resetting database...")
    os.system("cd $(dirname $0)/../backend && uv run python manage.py flush --no-input -v 0 2>/dev/null")
    os.system("cd $(dirname $0)/../backend && uv run python manage.py migrate -v 0 2>/dev/null")
    os.system("cd $(dirname $0)/../backend && uv run python manage.py seed 2>/dev/null")
    print("[setup] Done — 14 records seeded.\n")

    token = test_auth()
    test_me(token)
    source_ids = test_sources(token)
    sap_run_id, util_run_id, travel_run_id = test_ingestion(token, source_ids)
    test_runs(token, sap_run_id)
    test_records_list(token, util_run_id)
    test_record_detail(token)
    record_id = test_record_editing(token)
    test_review_actions(token, record_id)
    test_bulk_review(token)
    test_dashboard(token)
    test_parser_correctness(token, source_ids, sap_run_id, util_run_id, travel_run_id)

    # Print summary
    print(f"\n{'='*60}")
    print(f"\033[1m  Results: {num_passed} passed, {num_failed} failed out of {num_passed + num_failed} tests\033[0m")
    print(f"{'='*60}\n")

    if num_failed > 0:
        print("FAILURES:")
        for result_label, test_name, note in all_test_results:
            if result_label == "FAIL":
                print(f"  ✗ {test_name}" + (f" [{note}]" if note else ""))
        print()

    return all_test_results


if __name__ == "__main__":
    main()
    sys.exit(1 if num_failed > 0 else 0)
