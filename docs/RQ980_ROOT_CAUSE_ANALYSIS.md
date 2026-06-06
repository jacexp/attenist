# RQ980 — Root Cause Analysis

## 1. Database Query

```sql
SELECT emp_id, emp_name, sheet_name, rank, row_number
FROM employees WHERE emp_id = 'RQ980';
```

| emp_id | emp_name | sheet_name | rank | row_number |
|--------|----------|------------|------|------------|
| RQ980 | RENUKA | TESS-2 TERRIER | ACOP | 66 |

**Single row, no duplicates.** The database has exactly one RQ980 record on `TESS-2 TERRIER`.

---

## 2. Workbook Search

| Worksheet | Row | Col B (emp_id) | Col C (name) | Col D (rank) |
|-----------|-----|----------------|--------------|-------------|
| **TESS-2 TERRIER** | 66 | RQ980 | RENUKA | ACOP |
| Shif (2) | 36 | RP690 | RENUKA MR | LGA |

**RQ980 appears only in `TESS-2 TERRIER`** worksheet, row 66.

A similarly-named employee `RP690` (RENUKA MR) appears in BOTH `TESS-2 TERRIER` (row 157) and `Shif (2)` (row 36).

---

## 3. Import Mapping (sheet_name assignment)

**File:** `workbook/indexes/employee.py:31`

```python
sheet_name=sheet.title,
```

The import uses `openpyxl`'s `sheet.title` property directly, with no normalization or stripping.

**Workbook vs DB sheet names — byte-exact match confirmed:**

| Workbook (via openpyxl) | DB (via sqlite3) | Length | Match |
|---|---|---|---|
| `'TESS-2 TERRIER'` | `'TESS-2 TERRIER'` | 14 | ✅ Exact |
| `'Shif (2)'` | `'Shif (2)'` | 8 | ✅ Exact |
| `'Sheet1'` | `'Sheet1'` | 6 | ✅ Exact |
| `'Summary '` | (not in DB — no employees) | 8 | N/A |

**Import mapping is correct.** RQ980 was correctly assigned `sheet_name = 'TESS-2 TERRIER'`.

---

## 4. Error Trace

The error from the user:

```
Cannot match employee RQ980 from sheet 'SHIFT 2' to active sheet 'TESS-2 TERRIER'
```

Actual error text (from `validation_service.py:201-205`):

```python
raise ValueError(
    f"Cannot match employee {selected_employee.employee_id} "
    f"from sheet '{selected_employee.sheet_name}' "
    f"to active sheet '{sheet_name}'."
)
```

`'SHIFT 2'` in the user's report is a paraphrase of the workbook's sheet name `'Shif (2)'`.

---

## 5. Root Cause

**The error is caused by a safety-check inconsistency in `EmployeeSearchDialog.select_employee()`** (`ui/ocr_attendance_tab.py:190-212`).

Current code:

```python
def select_employee(self):
    current_item = self.results_list.currentItem()
    if current_item:
        emp = current_item.data(Qt.UserRole)
        # Hard safety: verify sheet before applying
        if self.scope_toggle.isChecked() and self.sheet_name:
            if emp.sheet_name != self.sheet_name:
                QMessageBox.warning(...)
                return
        self.selected_employee = emp
        self.accept()
```

**The safety check is conditional on `self.scope_toggle.isChecked()`** — it only runs when "Active Sheet Only" mode is ON. When the user switches to "All Sheets" mode, the check is **completely bypassed**.

The downstream `manual_correction()` (`validation_service.py:193-205`) **always** checks:

```python
elif selected_employee:
    if sheet_name and selected_employee.sheet_name != sheet_name:
        raise ValueError(...)
```

### Result: Inconsistency

| Mode | Dialog safety check | `manual_correction` check | Outcome |
|------|---------------------|---------------------------|---------|
| Active Sheet Only | ✅ Enforced | ✅ Enforced | Works |
| **All Sheets** | **❌ Bypassed** | **✅ Enforced** | **Crash with ValueError** |

### Trigger Scenario

1. User runs OCR on `TESS-2 TERRIER` sheet
2. An OCR record reads an employee whose ID exists on `'Shif (2)'` in the DB (not on `TESS-2 TERRIER`)
3. The record is `UNMATCHED` (cross-sheet, so `_find_exact_match` returns None)
4. User clicks "Change Match"
5. Active sheet is `TESS-2 TERRIER`, dialog opens in "Active Sheet Only" mode
6. The employee does NOT appear (not on this sheet)
7. User switches to "All Sheets" mode
8. Employee appears, user selects it
9. **Dialog lets the selection through** (mode is "All Sheets" → check skipped)
10. `manual_correction` raises `ValueError` → user sees traceback

### Why `'SHIFT 2'` and not `'Shif (2)'`?

The user may have been working with a **different workbook** (not `samples/test1.xlsx`), where the employee RQ980 actually resides on a sheet named `'Shif (2)'` or similar. The same dialog bypass applies regardless of which workbook is used.

---

## 6. Decision: Which is Wrong?

| Hypothesis | Verdict |
|------------|---------|
| **A. Database is correct, user selected wrong employee** | **PARTIALLY** — DB is correct (RQ980 is on `TESS-2 TERRIER`), but the dialog allowed selecting an employee from a different sheet |
| **B. Database import assigned incorrect sheet_name** | **FALSE** — Import correctly uses `sheet.title`, verified byte-exact |
| **C. OCR validation is searching wrong scope** | **FALSE** — OCR validates against the correct active sheet |

**Root cause: Bug in `EmployeeSearchDialog.select_employee()` — the sheet safety check must always run, not only in "Active Sheet Only" mode.**

---

## 7. Required Fix

In `ui/ocr_attendance_tab.py`, change `select_employee()`:

**Before:**
```python
if self.scope_toggle.isChecked() and self.sheet_name:
    if emp.sheet_name != self.sheet_name:
        ...
```

**After:**
```python
if self.sheet_name:
    if emp.sheet_name != self.sheet_name:
        ...
```

Remove the `self.scope_toggle.isChecked()` condition. The safety check must always enforce that the selected employee belongs to the active worksheet, regardless of the "All Sheets" toggle. The "All Sheets" mode should remain available as a **discovery tool** — users can search across sheets to find employees, but can only select those belonging to the active sheet.
