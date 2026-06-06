# Formula Commit Trace

## Real failing employee: BK447 — real workbook: samples/test1.xlsx

---

### 1. Workbook Load

| Field | Value |
|---|---|
| `workbook path` | `/tmp/formula_trace/test1_COPY.xlsx` (copy of `samples/test1.xlsx`) |
| Load mode | `load_workbook(path)` → `data_only=False` (production default) |

### 2. Indexes Built

```
DateIndexer dates:     {10:12, 11:13, 12:14, ..., 31:33}
                         (int-value dates only — days 1-9 are strings in row 5)
Employee:              BK447 / BULBUL KUMARI  →  sheet='Shif (2)'  row=13
```

### 3. OCR Result → Employee Lookup

| Field | Value |
|---|---|
| OCR detected text | `BK447` |
| `employee_id` | `BK447` |
| `name` | `BULBUL KUMARI` |
| `sheet_name` | `'Shif (2)'` |
| `row` | `13` |

### 4. Target Sheet

| Field | Value |
|---|---|
| `employee.sheet_name` | `'Shif (2)'` |
| `active_sheet_name` | `'Shif (2)'` |
| Sheet match | `True` |

### 5. Target Row

| Field | Value |
|---|---|
| `employee.row` | `13` |

### 6. Target Column

| Field | Value |
|---|---|
| `day` (from UI) | `11` |
| `dates[11]` | `13` |
| Column letter | `M` |

### 7. Target Cell — Before Write

| Field | Value |
|---|---|
| `cell address` | **M13** |
| `cell.value` | `'=F13'` |
| `cell.data_type` | `'f'` |
| Formula present? | **YES** |
| Formula text | `=F13` |
| References cell | **F13** (employee BK447, Day 2) |
| Source F13.value | `'WO'` |
| Source F13.data_type | `'s'` (direct value) |

### 8. During Write

| Field | Value |
|---|---|
| Requested attendance value | `'AB'` |
| `_get_evaluated_value(M13)` | `'WO'` (resolves `=F13` → reads F13 → returns `'WO'`) |
| This value is | **return value only** — not used for write targeting |
| Actual write destination | **M13** (the formula cell itself) |
| Write code | `cell.value = 'AB'` |

### 9. Target Cell — After Write (in-memory)

| Field | Value |
|---|---|
| `cell.value` | `'AB'` |
| `cell.data_type` | `'s'` |
| Formula present? | **NO — 🔴 DESTROYED** |

### 10. Workbook Save

| Field | Value |
|---|---|
| Save result | **SUCCESS** |
| Saved to | `/tmp/formula_trace/after_commit.xlsx` |

### 11. Re-Open Workbook from Disk

| Field | Value |
|---|---|
| `value after save` | `'AB'` |
| `formula after save` | `None` (not a formula) |
| `data_type after save` | `'s'` |
| `displayed value` (`data_only=True`) | `'AB'` |
| Formula present? | **NO — 🔴 DESTROYED ON DISK** |
| Source F13 value | `'WO'` (untouched, orphaned) |

---

### Comparison Table

| Property | Before | After (memory) | After (disk) |
|---|---|---|---|
| `cell.address` | M13 | M13 | M13 |
| `cell.data_type` | `'f'` | `'s'` | `'s'` |
| `cell.value` | `'=F13'` | `'AB'` | `'AB'` |
| `is_formula` | **True** | **False** | **False** |
| `formula_text` | `'=F13'` | `None` | `None` |

---

## Root Cause

```
services/attendance_service.py:46 — cell.value = shift
```

The single assignment `cell.value = shift` **unconditionally overwrites** the cell's contents. If the cell holds a formula (`data_type='f'`, value starts with `'='`), the formula string is destroyed and replaced with a static shift string.

`_get_evaluated_value()` correctly resolves `=F13` → reads F13 (value=`'WO'`) → returns `'WO'`. But this resolved value is **only used as the return value** of `mark()`. It is never used to decide **where** to write. The write always targets the formula cell (M13) instead of the source data cell (F13).

**The formula `=F13` is destroyed in memory, persisted to disk, and confirmed gone after re-open.** The source cell F13 (`'WO'`) remains untouched but is now orphaned — no cell references it.
