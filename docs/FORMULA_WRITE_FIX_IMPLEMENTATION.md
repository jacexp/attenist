# Formula Write Fix Implementation

## Files Modified

| File | Change |
|------|--------|
| `services/attendance_service.py` | Formula resolution, write redirection, diagnostics |

---

## Algorithm

### `_resolve_formula_chain(cell, sheet, visited=None)`

Recursively resolves a formula cell to its final non-formula source.

```
Input:  cell (openpyxl Cell), sheet (openpyxl Worksheet)
Output: (source_cell, chain_list)

1. Add (cell.row, cell.column) to visited set
2. If cell is NOT a formula → return (cell, [cell])  [base case]
3. If formula is NOT a simple =A1 reference → raise ValueError
4. Parse =A1 to extract (ref_col, ref_row)
5. If ref_col < 1 or ref_row < 1 → raise ValueError
6. Get referenced cell from sheet
7. If referenced cell IS a formula → recurse
8. Else → return (ref_cell, [cell, ref_cell])

Circular reference detection:
  If (cell.row, cell.column) already in visited → raise ValueError
```

### `mark()` — Modified Write Path

```
Before:  cell.value = shift           [writes to display cell]
After:
  1. Get target_cell from (employee.row, date column)
  2. If target_cell is a formula:
       source_cell, chain = _resolve_formula_chain(target_cell)
       write to source_cell
  3. Else:
       write to target_cell (unchanged)
  4. Log write trace with employee, target, chain, source, old/new values
```

---

## Guard Behavior

| Formula Type | Example | Result |
|---|---|---|
| Simple ref | `=F13` | Resolved, written to source |
| Chain ref | `=M13` (→ `=F13`) | Fully resolved, written to final source |
| `=IF(...)` | `=IF(E15="","",E15)` | Rejected: "Complex formula detected" |
| `=COUNTIF(...)` | `=COUNTIF(E6:AI6,"A")` | Rejected: "Complex formula detected" |
| `=SUM(...)` | `=SUM(F13:G13)` | Rejected: "Complex formula detected" |
| `=VLOOKUP(...)` | `=VLOOKUP(A10,B:C,2,FALSE)` | Rejected: "Complex formula detected" |
| Circular | `A1=B1`, `B1=A1` | Rejected: "Circular reference detected" |
| Self-loop | `A1=A1` | Rejected: "Circular reference detected" |
| Row 0 ref | `=A0` | Rejected: "Invalid reference" |

---

## Real-Workbook Verification

### Test: BK447 — Direct Formula (M13 = =F13)

```
Before: M13 = '=F13' (formula), F13 = 'WO' (value)
Write:  mark(BK447, day=11, shift='X')

WRITE TRACE:
  Employee=BK447  Name=BULBUL KUMARI  Sheet=Shif (2)
  Target=M13  Chain=M13 -> F13  ResolvedSource=F13
  OldValue='WO'  NewValue='X'

After:  M13 = '=F13' (formula preserved ✓)
        F13 = 'X'   (source updated ✓)
On disk:M13 = '=F13' (formula persisted ✓)
        F13 = 'X'    (value persisted ✓)
```

### Test: BK447 — Chain Formula (T13 = =M13 → =F13)

```
Before: T13 = '=M13' (formula), M13 = '=F13' (formula), F13 = 'X' (value)
Write:  mark(BK447, day=18, shift='Y')

WRITE TRACE:
  Employee=BK447  Name=BULBUL KUMARI  Sheet=Shif (2)
  Target=T13  Chain=T13 -> M13 -> F13  ResolvedSource=F13
  OldValue='X'  NewValue='Y'

After:  T13 = '=M13' (formula preserved ✓)
        M13 = '=F13' (formula preserved ✓)
        F13 = 'Y'    (source updated ✓)
On disk:T13 = '=M13' (formula persisted ✓)
        M13 = '=F13' (formula persisted ✓)
        F13 = 'Y'    (value persisted ✓)
```

---

## Test Results

All 12 unit tests pass:

```
tests/test_formula_write.py::TestDirectFormula::test_resolves_to_source_cell       PASSED
tests/test_formula_write.py::TestDirectFormula::test_old_value_from_source         PASSED
tests/test_formula_write.py::TestDirectFormula::test_non_formula_cell_unaffected   PASSED
tests/test_formula_write.py::TestChainFormula::test_resolves_full_chain            PASSED
tests/test_formula_write.py::TestChainFormula::test_old_value_from_final_source    PASSED
tests/test_formula_write.py::TestComplexFormula::test_raises_error                 PASSED
tests/test_formula_write.py::TestComplexFormula::test_raises_on_if                 PASSED
tests/test_formula_write.py::TestComplexFormula::test_raises_on_sum                PASSED
tests/test_formula_write.py::TestCircularReference::test_direct_circular           PASSED
tests/test_formula_write.py::TestCircularReference::test_indirect_circular         PASSED
tests/test_formula_write.py::TestInvalidReference::test_invalid_row_zero           PASSED
tests/test_formula_write.py::TestSaveAndReopen::test_save_preserves_formulas       PASSED
```

### Test Coverage

| Case | Status |
|------|--------|
| Direct formula: M13 = =F13 → write to F13, preserve =F13 | ✓ |
| Source old value returned correctly | ✓ |
| Non-formula cells unaffected | ✓ |
| Chain formula: T13 = =M13 → =F13 → write to F13, preserve both | ✓ |
| Chain old value from final source | ✓ |
| Complex formula (=COUNTIF) → abort with clear error | ✓ |
| Complex formula (=IF) → abort with clear error | ✓ |
| Complex formula (=SUM) → abort with clear error | ✓ |
| Circular reference (A1=B1, B1=A1) → abort with clear error | ✓ |
| Self-loop (A1=A1) → abort with clear error | ✓ |
| Invalid reference (=A0) → abort with clear error | ✓ |
| Save + reopen preserves formulas on disk | ✓ |

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| No formulas destroyed | ✓ |
| Source attendance updated correctly | ✓ |
| Formula chains preserved | ✓ |
| Workbook saves successfully | ✓ |
| OCR and Manual attendance paths both work | Both paths call `mark()` — fix applies to both |
| Existing workbook structure remains unchanged | ✓ — only `attendance_service.py` modified |
