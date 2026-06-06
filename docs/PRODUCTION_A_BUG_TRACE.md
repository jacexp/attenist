# PRODUCTION_A_BUG_TRACE

## Executive Summary

**Bug**: Operators report "missing attendance recognition" for some attendance values containing 'A'.

**Root Cause**: Audit log shows formula strings (e.g., `'=F13'`) instead of evaluated values (e.g., `'WO'`).

**Fix Applied**: Added `_get_evaluated_value()` method in `services/attendance_service.py` to resolve simple cell references when reading attendance values for audit logging.

---

## Failing Cell Details

### Actual Workbook Cell
- **Workbook**: `samples/JUN 26 Terrier MDR 2026 REGISTER.xlsx`
- **Sheet**: `Shif (2)`
- **Coordinate**: `M13`
- **Employee**: `BULBUL KUMARI` (ID: BK447)
- **Day**: 11
- **Row**: 13
- **Column**: 13 (M)

### Values
| Aspect | Value |
|--------|-------|
| **Excel Visible Value** | `WO` |
| **OpenPyXL Raw Value** | `=F13` |
| **Cell data_type** | `f` (formula) |
| **Referenced Cell** | `F13` |
| **Referenced Cell Value** | `WO` |

---

## Failing Code Path

### Function: `AttendanceService.mark()`
**File**: `services/attendance_service.py`
**Lines**: 17-36 (modified)

### Code Path Trace
```
1. User clicks "Mark Attendance"
2. MainWindow.mark_attendance() called (ui/main_window.py:201)
3. shift = self.shift_combo.currentText() -> "A" (ui/main_window.py:211)
4. attendance_service.mark(employee, day, shift) called (ui/main_window.py:215)
5. AttendanceService.mark() executes:
   a. sheet = workbook[employee.sheet_name] (line 23)
   b. column = self.dates[day] -> 13 (line 25)
   c. cell = sheet.cell(row=13, column=13) -> M13 (line 27-30)
   d. old_value = cell.value -> RETURNS '=F13' (line 32) <-- BUG HERE
   e. cell.value = shift -> writes 'A' (line 34)
   f. return old_value -> returns '=F13' (line 36)
6. MainWindow logs: logging.info(f"'{old_value}' -> '{shift}'") (ui/main_window.py:225)
   Result: Audit log shows "'=F13' -> 'A'" instead of "'WO' -> 'A'"
```

---

## Root Cause

The cell M13 contains a formula `=F13` that references cell F13 which contains the value `'WO'`. 

When OpenPyXL reads the cell with default settings (`data_only=False`):
- `cell.value` returns the formula string `'=F13'`
- `cell.data_type` returns `'f'`

The audit log was recording this formula string instead of the evaluated value that operators see in Excel.

---

## Exact Function Responsible

**Function**: `AttendanceService.mark()`
**File**: `services/attendance_service.py`
**Line**: 32 (original: `old_value = cell.value`)

This is the ONLY location in the codebase where attendance values are read for interpretation/display purposes.

---

## Fix Applied

### Modified File
`services/attendance_service.py`

### Changes
1. Added `_get_evaluated_value(cell)` method (lines 17-39)
2. Modified `mark()` method to use `_get_evaluated_value()` (line 48)

### Implementation
```python
def _get_evaluated_value(self, cell):
    """Get evaluated value for formula cells, otherwise return cell.value."""
    if cell.data_type == 'f' and isinstance(cell.value, str) and cell.value.startswith('='):
        formula = cell.value[1:]
        ref_col = 0
        ref_row = 0
        
        for char in formula:
            if char.isalpha():
                ref_col = ref_col * 26 + (ord(char.upper()) - ord('A') + 1)
            elif char.isdigit():
                ref_row = ref_row * 10 + int(char)
        
        if ref_col > 0 and ref_row > 0:
            ref_cell = cell.parent.cell(row=ref_row, column=ref_col)
            if ref_cell.data_type == 'f' and isinstance(ref_cell.value, str) and ref_cell.value.startswith('='):
                return self._get_evaluated_value(ref_cell)
            return ref_cell.value
    
    return cell.value
```

### Logic
1. Check if cell is a formula (`data_type == 'f'`)
2. Parse simple cell reference (e.g., `=F13` -> column 6, row 13)
3. Read the referenced cell
4. If referenced cell is also a formula, recurse
5. Return the evaluated value from the final referenced cell

---

## Constraints Satisfied

✅ **No WorkbookLoader changes** - `data_only=True` not used  
✅ **No save behavior changes** - formulas preserved in unmodified cells  
✅ **No formula replacement** - only reads evaluated value for audit log  
✅ **Workbook integrity maintained** - formulas remain intact  

---

## Impact

- **Audit logs now show correct "before" values**: `'WO' -> 'A'` instead of `'=F13' -> 'A'`
- **Operators see accurate attendance history**
- **No functional changes to attendance marking**
- **All existing tests pass**
- **Formula chains handled** (e.g., `=M13` -> `=F13` -> `WO`)
