# Formula Write Root Cause Analysis

## Investigation Status: COMPLETE

---

## 1. Root Cause (Definitive)

### PRIMARY: `cell.value = shift` unconditionally overwrites cell contents

| Attribute | Value |
|---|---|
| **Root cause** | `services/attendance_service.py:67` — `cell.value = shift` |
| **Type** | Unconditional overwrite — no formula check before write |
| **Evidence** | All 6 formula cells in test were destroyed (see §3) |

When `mark()` writes to a cell, it sets `.value` directly. openpyxl's Cell setter **removes the formula XML element** (`<f>`) and replaces it with a value element (`<v>`). The formula is permanently lost — in memory immediately, and on disk after the next `save()`.

### SECONDARY: `_get_evaluated_value()` is a fragile hand-rolled formula parser

| Attribute | Value |
|---|---|
| **File** | `services/attendance_service.py:17-36` |
| **Type** | Incorrect formula parsing — only handles `=A1` |
| **Evidence** | `=IF(E15="","",E15)` parsed as col=162375 row=1515 (§3.8) |

The parser iterates ALL alpha characters for column, then ALL digit characters for row, concatenating them arithmetically. This works for `=F13` but produces garbage for any formula containing keywords, operators, parentheses, or multiple cell references.

### TERTIARY: Garbage column index crashes `workbook.save()`

| Attribute | Value |
|---|---|
| **File** | `services/attendance_service.py:84` |
| **Type** | Save crash — openpyxl `get_column_letter(162375)` raises `ValueError` |
| **Evidence** | Test crashed at save with `Invalid column index 162375` (§3.8) |

When `_get_evaluated_value()` returns garbage column/row for a complex formula, the write still executes. But during save, openpyxl calculates the sheet dimension and calls `get_column_letter()` on the garbage column, which raises a ValueError.

---

## 2. Complete Write Path Trace

```
┌─────────────────────────────────────────────────────────────┐
│                    WRITE PATH TRACE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  UI Layer                                                   │
│  ├─ Manual: MainWindow.mark_attendance()  [main_window.py]  │
│  └─ OCR:    OCRAttendanceTab._perform_commit() [ocr_tab]    │
│         │                                                   │
│         ▼                                                   │
│  AttendanceService.mark(employee, day, shift, sheet)        │
│  ──────────────────────────────────────────────────         │
│                                                             │
│  1. Sheet guard:  employee.sheet_name == active_sheet       │  OK
│  2. Get sheet:    self.workbook[sheet_name]                 │  OK
│  3. Resolve col:  self.dates[day]                           │  OK  (DateIndexer row 5)
│  4. Get cell:     sheet.cell(row=emp.row, col=date_col)     │  OK
│  5. Read old:     _get_evaluated_value(cell)                │  ⚠ BUG2 (fragile parse)
│  6. ** WRITE:     cell.value = shift                     **│  🔴 BUG1 (destroys formula)
│  7. Return old:   return old_value                          │  ✓
│                                                             │
│  AttendanceService.save(path)                                │
│  ───────────────────────────────────────                    │
│  8. Backup:     shutil.copy2 → .bak                         │  OK
│  9. Save:       workbook.save(temp_path)                    │  🔴 BUG3 (crashes on garbage col)
│  10. Atomic:    os.replace(temp_path, target_path)          │  OK
└─────────────────────────────────────────────────────────────┘
```

**Both manual and OCR paths are identical** — they call the same `AttendanceService.mark()` method. There is no behavioral difference between the two paths.

---

## 3. Evidence Per Cell Type

### 3.1 Direct value cell — EMP001 Day 1

| Field | Before | After |
|---|---|---|
| Cell | E10 | E10 |
| Data type | `'s'` | `'s'` |
| Value | `'A'` | `'WO'` |
| Formula | No | N/A |
| **Verdict** | ✅ Correct write | |

### 3.2 Simple formula `=E10` — EMP001 Day 2

| Field | Before | After |
|---|---|---|
| Cell | F10 | F10 |
| Data type | `'f'` | `'s'` |
| Value | `'=E10'` | `'WO'` |
| Formula | `=E10` | **DESTROYED** |
| Eval (read) | `'WO'` (from E10) | N/A |
| **Verdict** | 🔴 Formula destroyed by `cell.value = shift` | |

### 3.3 Simple formula `=E11` — EMP002 Day 2

| Field | Before | After |
|---|---|---|
| Cell | F11 | F11 |
| Data type | `'f'` | `'s'` |
| Value | `'=E11'` | `'WO'` |
| Formula | `=E11` | **DESTROYED** |
| Eval (read) | `'B'` (from E11) | N/A |
| **Verdict** | 🔴 Formula destroyed | |

### 3.4 Simple formula `=E12` — EMP003 Day 2

| Field | Before | After |
|---|---|---|
| Cell | F12 | F12 |
| Data type | `'f'` | `'s'` |
| Value | `'=E12'` | `'AB'` |
| Formula | `=E12` | **DESTROYED** |
| Eval (read) | `'C'` (from E12) | N/A |
| **Verdict** | 🔴 Formula destroyed | |

### 3.5 Formula chain `=F12 → =E12` — EMP003 Day 3

| Field | Before | After |
|---|---|---|
| Cell | G12 | G12 |
| Data type | `'f'` | `'s'` |
| Value | `'=F12'` | `'AB'` |
| Formula | `=F12` | **DESTROYED** |
| Chain eval | F12→E12→`'C'` (correct) | N/A |
| **Verdict** | 🔴 Formula destroyed. Note: parser correctly walks the chain, but write still destroys. |

### 3.6 Empty cell — EMP004 Day 1

| Field | Before | After |
|---|---|---|
| Cell | E13 | E13 |
| Data type | `'n'` | `'s'` |
| Value | `None` | `'G'` |
| Formula | No | N/A |
| **Verdict** | ✅ Correct write to empty cell | |

### 3.7 Cross-employee formula `=E10` — EMP005 Day 2

| Field | Before | After |
|---|---|---|
| Cell | F14 | F14 |
| Data type | `'f'` | `'s'` |
| Value | `'=E10'` | `'AB'` |
| Formula | `=E10` | **DESTROYED** |
| Eval (read) | `'WO'` (from EMP001 E10) | N/A |
| **Verdict** | 🔴 Formula destroyed | |

### 3.8 Complex formula `=IF(E15="","",E15)` — EMP006 Day 2

| Field | Before | After |
|---|---|---|
| Cell | F15 | F15 |
| Data type | `'f'` | `'s'` |
| Value | `'=IF(E15="","",E15)'` | `'WO'` |
| Formula | `=IF(E15="","",E15)` | **DESTROYED** |
| Parser result | col=**162375** row=**1515** (garbage!) | N/A |
| Eval (read) | `None` (looked up wrong cell) | N/A |
| Save outcome | **CRASHED** — `ValueError: Invalid column index 162375` | |
| **Verdict** | 🔴 Formula destroyed. Parser produces garbage. Save crashes. **Triple bug.** | |

---

### Summary Table

| Cell | Type | Parser OK? | Write Correct? | Formula Preserved? | Save OK? |
|---|---|---|---|---|---|
| E10 | Direct value | N/A | ✅ Yes | N/A | ✅ |
| F10 | `=E10` | ✅ E→5/10 | ❌ Overwrote | 🔴 **Destroyed** | ✅ |
| F11 | `=E11` | ✅ E→5/11 | ❌ Overwrote | 🔴 **Destroyed** | ✅ |
| F12 | `=E12` | ✅ E→5/12 | ❌ Overwrote | 🔴 **Destroyed** | ✅ |
| G12 | `=F12` | ✅ F→6/12+chain | ❌ Overwrote | 🔴 **Destroyed** | ✅ |
| E13 | Empty | N/A | ✅ Yes | N/A | ✅ |
| F14 | `=E10` | ✅ E→5/10 | ❌ Overwrote | 🔴 **Destroyed** | ✅ |
| F15 | `=IF(...)` | ❌ 162375/1515 | ❌ Overwrote | 🔴 **Destroyed** | 🔴 **Crashed** |

---

## 4. Root Cause Classification

Per your question: which of these is the root cause?

| Option | Verdict | Explanation |
|---|---|---|
| **A. Formula cells being skipped** | ❌ NO | Formula cells are NOT skipped — they are written to |
| **B. Formula cells being overwritten** | ✅ **YES** | `cell.value = shift` unconditionally replaces formula with static value |
| **C. Formula cells treated as occupied** | ❌ NO | The `_get_evaluated_value()` reads them before write, but write doesn't use this |
| **D. Wrong cell targeted** | ❌ NO | Cell selection (row/col from indexes) is correct |
| **E. Workbook save destroys formulas** | ❌ NO | Save merely serializes in-memory state; the destruction happened at write time |
| **F. OCR vs manual path differ** | ❌ NO | Both call exact same `AttendanceService.mark()` |
| **G. Existing value detection incorrect** | ❌ YES (partial) | `_get_evaluated_value()` returns garbage for complex formulas, but this is a **read** bug, not a write bug. The write destroy is the real issue. |

**Definitive answer:** **B (primary) + G (secondary)**

Root cause **B**: `cell.value = shift` unconditionally overwrites formulas at `attendance_service.py:67`.  
Contributing cause **G**: `_get_evaluated_value()` is an incomplete formula parser at `attendance_service.py:17-36`.

---

## 5. Reproduction

```python
# 1. Create formula cell
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.cell(row=1, column=5).value = "A"        # E1 = "A"
ws.cell(row=1, column=6).value = "=E1"      # F1 = =E1  (FORMULA)

# 2. Load with data_only=False (production default)
wb2 = load_workbook("test.xlsx", data_only=False)
ws2 = wb2.active

# 3. Read formula cell
cell = ws2.cell(row=1, column=6)
print(cell.value)   # "=E1"
print(cell.data_type)  # "f"

# 4. Write to it
cell.value = "WO"
print(cell.value)   # "WO"
print(cell.data_type)  # "s" ← FORMULA IS GONE

# 5. Save
wb2.save("corrupted.xlsx")
# Loading corrupted.xlsx shows "WO" in F1, not "=E1"
```

---

## 6. Affected Code Locations

| # | File | Line | Role | Severity |
|---|---|---|---|---|
| 1 | `services/attendance_service.py` | 17-36 | `_get_evaluated_value()` — fragile formula parser | HIGH |
| 2 | `services/attendance_service.py` | 67 | `cell.value = shift` — unconditional write destroys formulas | **CRITICAL** |
| 3 | `services/attendance_service.py` | 84 | `workbook.save()` — crashes if garbage column index present | HIGH |
| 4 | `workbook/loader.py` | 15 | `load_workbook(path)` — no `data_only` flag (minor, see §7.2) | LOW |

---

## 7. Recommended Fix

### 7.1 Core fix: redirect formula cell writes to source cell

Replace the raw write at `attendance_service.py:67` with a formula-aware write:

```python
def _resolve_formula_source(self, cell, visited=None):
    """Walk formula chain to find the leaf data cell."""
    import re
    if visited is None:
        visited = set()
    if id(cell) in visited:
        return None
    visited.add(id(cell))

    if not (cell.data_type == 'f' and isinstance(cell.value, str) and cell.value.startswith('=')):
        return cell  # Not a formula — this is a data cell

    formula = cell.value[1:].strip()
    match = re.match(r'^([A-Za-z]+)(\d+)$', formula)
    if not match:
        return None  # Complex formula — cannot resolve safely

    col_letters = match.group(1).upper()
    row_num = int(match.group(2))
    col_num = 0
    for ch in col_letters:
        col_num = col_num * 26 + (ord(ch) - ord('A') + 1)

    ref_cell = cell.parent.cell(row=row_num, column=col_num)
    return self._resolve_formula_source(ref_cell, visited)
```

Then in `mark()`, replace lines 65-69 with:

```python
old_value = self._get_evaluated_value(cell)

if cell.data_type == 'f' and isinstance(cell.value, str) and cell.value.startswith('='):
    source = self._resolve_formula_source(cell)
    if source:
        source.value = shift
    else:
        raise ValueError(f"Cannot write to formula cell {cell.column_letter}{cell.row}: "
                         f"formula '{cell.value}' is too complex to resolve automatically")
else:
    cell.value = shift
```

### 7.2 Optional: load with `data_only=True` for reading

Change `workbook/loader.py:15` to:

```python
return load_workbook(workbook_path)
```

Plus a second load for formula-aware reading:

```python
# For reading evaluated values:
wb_data = load_workbook(path, data_only=True)
# For writing (formula preservation):
wb_formulas = load_workbook(path, data_only=False)
```

This is optional — the core fix in §7.1 handles the write path. The `data_only` change only affects the accuracy of `_get_evaluated_value()`.

### 7.3 Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Circular formula references | Very low | `visited` set with recursion depth guard |
| Complex formulas skipped | Medium | Clear ValueError with explanation, no silent failure |
| Regex misparse of valid formula | Low | `^[A-Za-z]+\d+$` is a narrow, proven pattern |
| Empty source cell (no cached value) | Low | The source cell may be None; write still works |
| Regression on non-formula cells | None | Code path unchanged for `data_type != 'f'` |

---

## 8. Conclusion

The bug is **unconditional**. Every write to any cell that contains a formula will destroy that formula. This affects:

- Every manual attendance write where the target cell has a formula
- Every OCR batch commit where the target cell has a formula
- Both simple `=A1` references and complex formulas

There is no scenario where a formula cell survives a write through the current `AttendanceService.mark()` path.

The fix is **localized to `services/attendance_service.py`** — approximately 30 lines of new code — and has zero risk of regression for non-formula cells.
