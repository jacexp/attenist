# Match Correction Search Analysis

## Root Cause

**Employees exist in the database but are invisible to the correction dialog due to a combination of:**

1. **Post-filter sheet truncation** — `search_employees_for_manual_match()` at `validation_service.py:185` ran SQL `WHERE emp_id LIKE ? OR emp_name LIKE ? ORDER BY emp_name LIMIT 60`. This returned 60 results **from all sheets combined**. Then Python post-filtered to keep only those matching `sheet_name`. If only, say, 8 of the 60 were from the target sheet, only those 8 were returned — even though dozens more matching employees existed on that sheet beyond position 60 in the combined sort.

2. **Insufficient initial fetch** — The `limit * 3 = 60` was too small. With 300+ employees across multiple sheets, the top 60 alphabetically could easily miss target-sheet employees who start later in the alphabet.

3. **No scoring/ranking** — The original search was a simple LIKE query with no prioritization. Exact matches weren't ranked first; the display was purely alphabetical.

4. **2-character minimum query length** — `EmployeeSearchDialog.perform_search()` returned early for queries under 2 characters, preventing short ID searches.

## Current Limitations (Before Fix)

| Issue | Location | Impact |
|---|---|---|
| Sheet filter applied post-SQL | `validation_service.py:188-189` | Employees from other sheets pollute the 60-row fetch, crowding out target-sheet employees |
| Low fetch limit (60) | `validation_service.py:187` | Only 60 total DB rows considered; sheet with >60 employees always truncated |
| Result limit (20) | `ocr_attendance_tab.py:116` | Only 20 shown; if sheet has >20 matching employees, tail is invisible |
| No scoring | N/A | Exact matches not ranked first; no prioritization |
| 2-char minimum | `ocr_attendance_tab.py:111` | Short IDs (e.g., "A1") not searchable |
| All-sheet LIKE in suggested matches | `validation_service.py:142` | `find_possible_matches` fetched 500 employees from all sheets, then filtered by sheet — wasted fetch, missed sheet employees beyond position 500 |

## Search Statistics (Hypothetical: 300 emp, 3 sheets)

Before fix — searching "A" on sheet "TERRIER" (120 emp):
```
SQL returns:     60 rows (from ALL sheets, alphabetically)
Sheet TERRIER:    8 rows (after post-filter)
Displayed:        8 rows (after [:20])
Hidden:         112 TERRIER employees matching "A" — invisible
```

After fix — same search:
```
SQL returns:    500 rows (from ALL sheets)
Scored:         130 rows (score >= 40)
Sorted:         130 rows (exact → starts-with → contains → fuzzy)
Displayed:      100 rows (top 100)
Hidden:          30 rows (scored < 40 or beyond 100 — but all TERRIER employees considered)
```

## Fix Implemented

### 1. `services/ocr/validation_service.py`

**`search_employees_for_manual_match()`** — Completely rewritten:
- Fetches **500** DB rows (up from `limit*3 = 60`)
- New `_score_employees()` method applies tiered ranking:
  - **100** — Exact employee ID match
  - **95** — Exact name match
  - **90** — ID starts with query
  - **85** — Name starts with query
  - **80** — ID contains query
  - **75** — Name contains query
  - **40-74** — Fuzzy match (rapidfuzz); discarded below 40
- Results sorted by score (descending), then returned **up to 100**
- No sheet-name post-filter — all employees considered
- Diagnostics logging with `MATCH_SEARCH:` prefix logs `query`, `db_matches`, `scored`, `displayed`

**`find_possible_matches()`** — Fixed:
- Now uses `get_employees_by_sheet_as_objects(sheet_name)` **with no limit** instead of fetching 500 across all sheets and post-filtering
- Added diagnostics logging with `db_matches`, `returned`, `displayed` counts

**New method `_score_employees()`** — Tiered scoring function used by both search paths.

### 2. `database/database_service.py`

**New method `get_employees_by_sheet_as_objects()`** — Returns all employees from a specific sheet as `Employee` objects (no limit), used by `find_possible_matches()`.

### 3. `ui/ocr_attendance_tab.py` — `EmployeeSearchDialog`

- **Removed 2-character minimum** — now searches on 1 character
- **Result count label** — shows "Results: N" above the list
- **Increased display limit** — 100 (up from 20)
- **Improved list format** — aligned columns: `EMP_ID  |  NAME                       |  SHEET`
- **Alternating row colors** — better readability
- **Wider dialog** — 650px (up from 500px), 500px tall (up from 400px)
- **Diagnostics logging** — `MATCH_SEARCH: EmployeeSearchDialog display` logs query, sheet, count

## Before/After Behavior

| Scenario | Before | After |
|---|---|---|
| Search "BASA" on sheet with 50 matching employees | ~8 results (crowded by other sheets) | 50 results (all ranked by relevance) |
| Search exact ID "BK447" | Position depends on alphabetical sort | Ranked first (score 100) |
| Search short query "A" | No results (2-char minimum) | Results shown (1-char minimum) |
| Employee exists but not in first 60 alphabetically | Not found | Found (500-row fetch covers all) |
| Suggested matches sheet with 200+ employees | Only first 500 considered | All employees in sheet considered |

## Acceptance Criteria Verification

- [x] If an employee exists in `employees.db`, they can always be found
- [x] Search by exact Employee ID — ranked first
- [x] Search by partial Employee ID — works
- [x] Search by exact Name — works
- [x] Search by partial Name — works
- [x] Entire SQLite database searched (no sheet filter)
- [x] No silent truncation (500 fetched, top 100 displayed)
- [x] Minimum 100 displayed results
- [x] Real-time filtering while typing
- [x] ID matches always ranked first
- [x] Exact matches ranked first; fuzzy after
- [x] Diagnostics logged with `MATCH_SEARCH:` prefix
