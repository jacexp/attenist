# Sheet-Scoped Matching — Verification Report

## Summary

**Status: ALL ACCEPTANCE CRITERIA PASS** — 14/14 sheet-scoping tests pass. Cross-sheet matches, corrections, and writes are impossible.

---

## Root Cause

Employee search and matching functions accepted a `sheet_name` parameter but ignored it, returning employees from ALL sheets. This created a serious data-integrity risk: OCR corrections and manual attendance marks could target the wrong employee on the wrong sheet.

## Files Modified

| File | Change |
|---|---|
| `database/employee_repository.py:241` | `search_employees()` now accepts optional `sheet_name`. SQL WHERE clause includes `AND sheet_name = ?` when provided. |
| `database/database_service.py:112` | `search_employees()` passes `sheet_name` to repository. |
| `database/database_service.py:119` | `search_employees_as_objects()` passes `sheet_name` to repository. |
| `services/ocr/validation_service.py:222` | `search_employees_for_manual_match()` — when `sheet_name` is provided, uses `get_employees_by_sheet_as_objects()` to fetch ONLY that sheet's employees before scoring. Sheet param was previously accepted but completely ignored. |
| `services/ocr/validation_service.py:130` | `_find_exact_match()` — added SHEET_SCOPED diagnostics logging (matched/rejected). Already filtered by sheet. |
| `services/ocr/validation_service.py:167` | `manual_correction()` — added `sheet_name` parameter. When `selected_employee` is used, validates `emp.sheet_name == sheet_name`. When `corrected_id` is used, passes `sheet_name` to `_validate_single_result()` for sheet-scoped lookup. Raises `ValueError` on cross-sheet correction. |
| `services/search_service.py:36` | `SearchService.search()` — passes `sheet_name` to DB-level search instead of relying solely on post-filter. Fuzzy fallback also double-checks sheet. |
| `ui/ocr_attendance_tab.py:282` | `accept_match()` — passes `sheet_name=self.sheet_name` to `manual_correction()`. |
| `ui/ocr_attendance_tab.py:292` | `change_match()` — passes `sheet_name=self.sheet_name` to `manual_correction()`. |
| `ui/ocr_attendance_tab.py:113` | `EmployeeSearchDialog.perform_search()` — added SHEET_SCOPED logging with active_sheet and cross-sheet detection. |

## Protection Layers (Defense in Depth)

| Layer | Path | What Protects |
|---|---|---|
| **DB query** | `employee_repository.search_employees()` | SQL `WHERE sheet_name = ?` |
| **Service fetch** | `validation_service.search_employees_for_manual_match()` | Uses `get_employees_by_sheet_as_objects()` |
| **Exact match** | `validation_service._find_exact_match()` | Rejects if `emp.sheet_name != sheet_name` |
| **Manual correction** | `validation_service.manual_correction()` | Raises `ValueError` on sheet mismatch |
| **Attendance write** | `attendance_service.mark()` | Raises `ValueError` on sheet mismatch |
| **SearchService** | `search_service.search()` | DB-level + post-filter + fuzzy fallback all sheet-scoped |

## Test Results

### Sheet scoping verification: 14/14 PASS

| Test | Result |
|---|---|
| Cross-sheet search returns zero wrong-sheet results | ✓ PASS |
| Same-sheet search returns only correct sheet | ✓ PASS |
| Employee found in own sheet, not in other sheet | ✓ PASS |
| Empty query (all employees) returns only active sheet | ✓ PASS |
| No employee ID overlap between distinct sheets | ✓ PASS |
| `_find_exact_match` finds employee in own sheet | ✓ PASS |
| `_find_exact_match` rejects employee from wrong sheet | ✓ PASS |
| `manual_correction` rejects cross-sheet employee | ✓ PASS |
| `manual_correction` allows same-sheet employee | ✓ PASS |
| `find_possible_matches` returns only active-sheet employees | ✓ PASS |
| `find_possible_matches` includes the correct employee | ✓ PASS |
| `attendance_service.mark()` allows same-sheet write | ✓ PASS |
| `attendance_service.mark()` rejects cross-sheet write | ✓ PASS |
| Cross-sheet rejection message includes sheet names | ✓ PASS |

### All tests: 65/65 PASS

| Test Suite | Tests | Status |
|---|---|---|
| Unit tests (`test_formula_write.py`) | 12 | ✓ PASS |
| Formula verification (`verify_formula_fix.py`) | 39 | ✓ PASS |
| Sheet-scoped matching (`verify_sheet_scoped_matching.py`) | 14 | ✓ PASS |

## Acceptance Criteria

| Criterion | Status | Evidence |
|---|---|---|
| ✓ No cross-sheet matches | PASS | All search results scoped to active sheet |
| ✓ No cross-sheet corrections | PASS | `manual_correction` raises ValueError |
| ✓ No cross-sheet attendance writes | PASS | `mark()` checks `emp.sheet_name == active_sheet` |
| ✓ Active sheet enforced everywhere | PASS | All 6 search/match paths validated |
| ✓ OCR restricted to active sheet | PASS | `find_possible_matches`, `_find_exact_match`, `search_employees_for_manual_match` all sheet-scoped |
| ✓ Manual search restricted to active sheet | PASS | `EmployeeSearchDialog` + `SearchService` both sheet-scoped |

## Example Diagnostics Logs

```
SHEET_SCOPED: search_employees_for_manual_match query='BK144' active_sheet='Shif (2)' sheet_employees=12
SHEET_SCOPED: _find_exact_match rejected cross-sheet emp_id='BK144' emp_sheet='Shif (2)' active_sheet='Sheet1'
SHEET_SCOPED: REJECTED cross-sheet correction employee=BK144 emp_sheet='Shif (2)' active_sheet='Sheet1'
```
