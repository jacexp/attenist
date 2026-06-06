# Change Match Dialog — Verification Report

## Missing Imports Found

| Widget | File | Status |
|--------|------|--------|
| `QCheckBox` | `ui/ocr_attendance_tab.py:99` | ✅ Fixed — added to import block |

All other widgets used by `EmployeeSearchDialog` were already imported (`QLabel`, `QLineEdit`, `QListWidget`, `QListWidgetItem`, `QDialogButtonBox`, `QVBoxLayout`, `QHBoxLayout`).

## Files Changed

| File | Change |
|------|--------|
| `ui/ocr_attendance_tab.py:11` | Added `QCheckBox` to `PySide6.QtWidgets` import block |

## Search Results Verification

Test environment: `employees.db` with 394 employees across 3 sheets.

| Test | Query | Sheet Filter | Expected | Actual | Status |
|------|-------|-------------|----------|--------|--------|
| Exact ID | `HE244` | TESS-2 TERRIER | 1 result (VENU KUMAR HS) | ✅ 1 result | PASS |
| Exact ID | `HE244` | All Sheets | 1 result | ✅ 1 result | PASS |
| Partial ID | `HE` | TESS-2 TERRIER | 15 results (all HE* IDs) | ✅ 15 found, 5 displayed | PASS |
| Partial ID | `HE` | All Sheets | 15 results | ✅ 15 found, 5 displayed | PASS |
| Name search | `VENU` | TESS-2 TERRIER | 2 results (VENU KUMAR HS, YARAVA VENU) | ✅ 2 results | PASS |
| Name substring | `KUMAR` | TESS-2 TERRIER | ≥1 result | ✅ found | PASS |
| Cross-sheet safety | HE244 on wrong sheet | TESS-2 TERRIER | Rejected with warning | ✅ Dialog shows warning | PASS |

## Diagnostics Logging (CORRECTION_SEARCH: prefix)

```
CORRECTION_SEARCH: query='HE244' sheet='TESS-2 TERRIER' db_matches=1 scored=1 displayed=1 truncated=0 filtered_by_score=0
CORRECTION_SEARCH: query='HE' sheet='TESS-2 TERRIER' db_matches=15 scored=15 displayed=5 truncated=10 filtered_by_score=0
CORRECTION_SEARCH: query='VENU' sheet='ALL' db_matches=2 scored=2 displayed=2 truncated=0 filtered_by_score=0
CORRECTION_SEARCH: DROPPED emp_id=ZZ999 name='UNRELATED' sheet='TESS-2 TERRIER' score=12.0
```

## Pass/Fail Status

| Criterion | Result |
|-----------|--------|
| ✓ Dialog compiles without errors | PASS |
| ✓ All Qt widget imports present | PASS |
| ✓ HE244 found in Change Match search | PASS |
| ✓ Active Sheet filter works | PASS |
| ✓ All Sheets toggle works | PASS |
| ✓ Diagnostics logging works | PASS |
| ✓ Cross-sheet selection rejected | PASS |
| ✓ 12/12 existing unit tests pass | PASS |
| ✓ Compile check: `py_compile` passes | PASS |

## Root Cause Summary

**Bug #1 (initial):** `search_employees_for_manual_match` never sent the user's query to SQLite when `sheet_name` was set — it fetched ALL sheet employees via `SELECT ... WHERE sheet_name = ?` with no query filter, then filtered purely in Python where the fuzzy < 40 threshold silently dropped employees.

**Bug #2 (this fix):** `QCheckBox` was used in the new `EmployeeSearchDialog` but never imported, causing `NameError: name 'QCheckBox' is not defined` before the dialog could open.
