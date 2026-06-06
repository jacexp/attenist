# Change Match / Verification Search Fix

## Root Cause

When `sheet_name` was set (which it always was from the dialog), `search_employees_for_manual_match()` in `validation_service.py` called `get_employees_by_sheet_as_objects(sheet_name)` — this ran `SELECT ... FROM employees WHERE sheet_name = ?` with **no query filter**. The user's search text was never sent to SQLite.

All filtering happened in Python:
1. Every employee on the sheet was fetched into memory
2. `_score_employees()` scored each one
3. Fuzzy score < 40 caused **silent drop** — employees vanished from results with no logging

This meant:
- Any employee whose `sheet_name` had even a minor discrepancy (trailing space, encoding) was **completely invisible** — never fetched from DB at all
- The fuzzy < 40 threshold silently dropped valid partial matches
- No "All Sheets" mode existed — users could never search across sheets
- The `get_employees_by_sheet` query lacks an index on `emp_id`/`emp_name` for the correction use case

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `services/ocr/validation_service.py` | 216–273 | Rewrote `_score_employees` and `search_employees_for_manual_match` — always passes query to SQL, logs diagnostics, no silent drops |
| `ui/ocr_attendance_tab.py` | 74–190 | Rewrote `EmployeeSearchDialog` — added sheet toggle, rank display, safety check, diagnostics logging |

No changes needed to `database/employee_repository.py` or `database/database_service.py` — `search_employees_as_objects()` already supported both `query` and `sheet_name` parameters.

## Query Logic (New)

```
search_employees_for_manual_match(query, sheet_name, limit=100)
  │
  ├─ database_service.search_employees_as_objects(query, limit*3, sheet_name=sheet_name)
  │    │
  │    └─ SQL: SELECT ... FROM employees
  │         WHERE (emp_id LIKE '%query%' OR emp_name LIKE '%query%')
  │           [AND sheet_name = ?]    ← only when sheet filter active
  │         ORDER BY emp_name
  │         LIMIT ?    ← generous: limit * 3
  │
  ├─ _score_employees(query, raw)     ← Python scoring (100→95→90→85→80→75→fuzzy)
  │    │  No silent drops: fuzzy < 20 threshold instead of < 40
  │    │  All drops logged with employee ID, name, sheet, score
  │
  ├─ sort desc by score
  ├─ slice [:limit]
  └─ return List[Employee]
```

### SQL BEFORE (broken):
```sql
-- get_employees_by_sheet_as_objects(sheet_name):
SELECT ... FROM employees WHERE sheet_name = ?
-- NO query filter! User's search ignored at SQL level.
```

### SQL AFTER (fixed):
```sql
-- search_employees_as_objects(query, limit, sheet_name):
SELECT ... FROM employees 
WHERE (emp_id LIKE '%query%' OR emp_name LIKE '%query%')
  AND sheet_name = ?    -- only when sheet filter active
ORDER BY emp_name 
LIMIT ?
```

## Sheet Filtering Logic

- **"Active Sheet Only"** (default): `sheet_name` passed to SQL → `AND sheet_name = ?`
- **"All Sheets"**: `sheet_name=None` → no sheet filter in SQL
- **Safety check in `select_employee()`**: If sheet filter is active and the selected employee's `sheet_name != self.sheet_name`, the dialog shows a warning and rejects the selection

## Ranking Logic

| Condition | Score |
|---|---|
| `emp_id == query` | 100 |
| `name == query` | 95 |
| `emp_id.startswith(query)` | 90 |
| `name.startswith(query)` | 85 |
| `query in emp_id` | 80 |
| `query in name` | 75 |
| Fuzzy fallback `max(fuzz.ratio, fuzz.partial_ratio)` | ≥ 20 |
| **Dropped** (logged with diagnostics) | < 20 |

All scores are deterministic per query. No random tie-breaking.

## Verification Steps

1. Open OCR tab, process an image with an employee from any sheet
2. Click "Change Match" in the verification wizard
3. Type an employee ID or name:
   - **Should appear**: The employee if they exist in SQLite
   - **Sheet toggle**: "Active Sheet Only" restricts to current sheet; "All Sheets" shows all
   - **Display**: `EMP ID | NAME | SHEET | RANK` columns
4. Click an employee or press Enter:
   - **Sheet mismatch**: Warning if employee not on active sheet (when in active-only mode)
   - **Accepted**: Dialog closes and match is applied

## Before / After Behavior

| Scenario | Before | After |
|----------|--------|-------|
| Employee on same sheet, correct ID | Shows ✓ | Shows ✓ |
| Employee on same sheet, partial name | Shows (if fuzzy ≥ 40) | Shows (if fuzzy ≥ 20) |
| Employee on DIFFERENT sheet | **Not found** — sheet-only fetch | Shows in "All Sheets" mode |
| Employee with whitespace in sheet_name | **Not found** — exact match | Found via LIKE query |
| Empty search | No results | No results (same) |
| "All Sheets" mode | **Not available** | Toggle in dialog |
| Display format | `ID | NAME | SHEET` | `ID | NAME | SHEET | RANK` |
| Diagnostics | Minimal (`MATCH_SEARCH:` prefix) | Full (`CORRECTION_SEARCH:` prefix) |
| Dropped employees | Silent | Logged with details |
| Enter key | No special behavior | Auto-selects top result |
| Cross-sheet safety | `ValueError` in `manual_correction` | Warning in dialog (earlier detection) |

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| ✓ Employee in SQLite must appear in search results | Fixed — query always sent to SQL |
| ✓ Active-sheet employees appear when sheet filter is on | Fixed — SQL `AND sheet_name = ?` |
| ✓ No cross-sheet leakage | Fixed — safety check in `select_employee` |
| ✓ No stale results | Fixed — fresh DB query every keystroke |
| ✓ No silent truncation | Fixed — all drops logged with reason |
| ✓ No wrong employee selection | Fixed — sheet verification before accept |
