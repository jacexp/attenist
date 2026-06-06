# Match Correction Search Fix

## Root Cause

The correction search had multiple gaps that could silently exclude valid employees:

### Gap 1: Query not normalized before SQL LIKE (HIGH)
The raw user query (including leading/trailing whitespace) was passed directly to `LIKE '%query%'`. A user typing `" HE244"` (accidental leading space) would get zero results because `LIKE '% HE244%'` does not match `HE244`.

### Gap 2: No exact-ID pre-lookup (HIGH)
The search relied entirely on `LIKE '%query%'` for every keystroke. There was no guaranteed path to find an employee by exact ID regardless of:
- Sheet scope (exact lookup bypasses sheet filter for discovery)
- LIKE wildcard interpretation (`_`, `%` in query)
- Whitespace issues (stripped before exact lookup)

### Gap 3: Fuzzy threshold dropped valid partial matches (MEDIUM)
The `_score_employees` function had a fuzzy threshold of `< 20` in the latest code (was `< 40` originally). While logged, the employee was still silently excluded from results. Threshold reduced to `< 10`.

### Gap 4: No deduplication across search paths (LOW)
If exact lookup and LIKE both returned the same employee, they could potentially appear twice.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `services/ocr/validation_service.py` | 216–316 | Rewrote `_score_employees` (threshold 40→10) and `search_employees_for_manual_match` (exact pre-lookup, strip, dedup) |

## Search Logic (New)

```
search_employees_for_manual_match(query, sheet_name, limit=100)
  │
  ├─ q = query.strip()
  │  If empty/whitespace → return []
  │
  ├─ Step 1: Exact ID match
  │  └─ database_service.get_employee_as_object(q.upper())
  │     Always runs. Bypasses sheet filter.
  │     Guarantees the employee appears in results for discovery.
  │     (Dialog safety check still prevents cross-sheet selection.)
  │
  ├─ Step 2: SQL LIKE search (broad)
  │  └─ database_service.search_employees_as_objects(q, 300, sheet_name)
  │     SQL: WHERE (emp_id LIKE '%q%' OR emp_name LIKE '%q%')
  │           [AND sheet_name = ?]
  │     Uses stripped query. Sheet-filtered when sheet_name is set.
  │
  ├─ Step 3: _score_employees(q, raw, diagnostics)
  │  Same hierarchical scoring: 100→95→90→85→80→75→fuzzy
  │  Fuzzy threshold: < 10 (was < 40, now very lenient)
  │  All drops logged with emp_id/name/sheet/score
  │
  ├─ Step 4: Merge + dedup
  │  results[emp_id] = (employee, max_score)
  │  Exact match (score 100) always preferred
  │
  ├─ sort desc by score → [:limit]
  └─ return [Employee, ...]
```

## Sheet Filtering Logic

| Mode | `sheet_name` passed to DB | Exact lookup | Safety check |
|------|---------------------------|-------------|--------------|
| Active Sheet Only | `"TESS-2 TERRIER"` | Runs (bypasses filter) | Enforced in dialog |
| All Sheets | `None` | Runs | Enforced in dialog |

The exact-ID pre-lookup always runs regardless of sheet mode. This is safe because:
1. The dialog shows the sheet name in results (`EMP ID | NAME | SHEET | RANK`)
2. The safety check in `select_employee()` rejects cross-sheet selections
3. Users can discover employees across sheets but cannot accidentally apply them

## Truncation Logic

| Stage | Limit | Logged |
|-------|-------|--------|
| SQL LIKE | `limit * 3` (300) | Via `like_matches` |
| Python scoring | `limit` (100) | Via `truncated_by_limit` |

Both limits are logged in diagnostics:
```
CORRECTION_SEARCH: query='HE' sheet='TESS-2 TERRIER' exact=none like_matches=15 scored=15 displayed=5 truncated=10 filtered_by_score=0
```

If truncation occurs (scored > displayed), `truncated_by_limit` shows how many were cut.

## Diagnostics Log Format

```
CORRECTION_SEARCH: query='<stripped>' sheet='<sheet or ALL>' exact=<ID or 'none'> like_matches=<N> scored=<N> displayed=<N> truncated=<N> filtered_by_score=<N>

CORRECTION_SEARCH: DROPPED emp_id=<ID> name='<NAME>' sheet='<SHEET>' score=<FLOAT>
```

## Before / After Behavior

| Scenario | Before | After |
|----------|--------|-------|
| Exact ID — employee on active sheet | Found via LIKE (if no whitespace issue) | Found via exact pre-lookup + LIKE |
| Exact ID — employee on DIFFERENT sheet | Not found (sheet filter hid it) | Found (exact lookup bypasses sheet filter) |
| Query with leading/trailing space | Not found (LIKE with space fails) | Found (stripped before both exact + LIKE) |
| Partial ID/name | Found (if string-matching conditions met) | Same (conditions unchanged) |
| Unrelated query (e.g., "ZZZZ") | Not found (LIKE returns 0) | Same (0 like_matches, logged) |
| Fuzzy-close query (fuzzy ratio 10-20) | Dropped silently | Logged with `DROPPED` prefix |
| Empty/whitespace-only | Returned empty | Same (early return) |
| Diagnostics | `CORRECTION_SEARCH: query=... db_matches=... scored=... displayed=...` | Same + `exact=... like_matches=...` |

## Verification

All 10 test scenarios pass:

| # | Test | Query | Sheet | Expected | Actual |
|---|------|-------|-------|----------|--------|
| 1 | Exact ID, sheet filter | `HE244` | TESS-2 TERRIER | 1 result | ✅ |
| 2 | Exact ID, all sheets | `HE244` | None | 1 result | ✅ |
| 3 | Exact ID, different sheet | `RQ980` | None | 1 result | ✅ |
| 4 | Leading space | ` HE244` | TESS-2 TERRIER | 1 result | ✅ |
| 5 | Partial ID | `HE` | TESS-2 TERRIER | 5 displayed | ✅ |
| 6 | Name search | `VENU` | TESS-2 TERRIER | 2 results | ✅ |
| 7 | Partial name | `KUMAR` | TESS-2 TERRIER | 5 displayed | ✅ |
| 8 | Empty query | `` | TESS-2 TERRIER | 0 results | ✅ |
| 9 | Whitespace only | `   ` | TESS-2 TERRIER | 0 results | ✅ |
| 10 | Non-matching | `ZZZZ` | TESS-2 TERRIER | 0 results (logged) | ✅ |
