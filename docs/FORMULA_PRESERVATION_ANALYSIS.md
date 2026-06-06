# FORMULA PRESERVATION ANALYSIS

## Executive Summary

**Formula Preservation Test Results**:

Loading a workbook with `data_only=True` and then saving it **DESTROYS all formulas**. The formulas are replaced with their evaluated static values.

**Critical Finding**: The simple fix of adding `data_only=True` to WorkbookLoader would cause data loss for any workbook containing formulas.

---

## Test Setup

### Source Workbook

- File: `samples/JUN 26 Terrier MDR 2026 REGISTER.xlsx`
- Sheet: `Shif (2)`
- Test cell: M13

### Cell States

**Original Cell M13**:
- Contains formula: `=F13`
- Formula evaluates to: `'WO'` (value in cell F13)

**Referenced Cell F13**:
- Contains direct value: `'WO'`
- This is the source of the formula result

---

## Test Procedure and Results

### Test 1: Verify Original Formula

```
Load workbook with data_only=False
Read cell M13

Result:
  cell.value = '=F13'
  cell.data_type = 'f' (formula)
```

**Status**: ✓ Original workbook contains formula

---

### Test 2: Read with data_only=True

```
Load workbook with data_only=True
Read cell M13

Result:
  cell.value = 'WO'
  cell.data_type = 's' (string)
```

**Status**: ✓ Formula evaluated correctly, returns 'WO'

---

### Test 3: Save After Loading with data_only=True

```
Load workbook with data_only=True
Save to new file
Reopen with data_only=False

Result:
  cell.value = 'WO'
  cell.data_type = 's' (string)
```

**Status**: ✗ **FORMULA LOST** - replaced with static value

---

### Test 4: Modify Cell and Save

```
Load workbook with data_only=True
Set cell.value = 'A'
Save to new file
Reopen with data_only=False

Result:
  cell.value = 'A'
  cell.data_type = 's' (string)
```

**Status**: ✓ Modification works, value saved correctly

---

## Detailed Test Output

### Step-by-Step Execution Log

```
================================================================================
FORMULA PRESERVATION TEST
================================================================================

Source workbook: samples/JUN 26 Terrier MDR 2026 REGISTER.xlsx
Test output: samples/formula_test_output.xlsx

--------------------------------------------------------------------------------
STEP 1: Find a cell with a formula
--------------------------------------------------------------------------------

Cell M13:
  data_only=False mode:
    cell.value = '=F13'
    cell.data_type = f

Referenced cell F13:
    cell.value = 'WO'
    cell.data_type = s

--------------------------------------------------------------------------------
STEP 2: Load with data_only=True
--------------------------------------------------------------------------------

Cell M13:
  data_only=True mode:
    cell.value = 'WO'
    cell.data_type = s

--------------------------------------------------------------------------------
STEP 3: Load with data_only=True and SAVE
--------------------------------------------------------------------------------

Before save:
    cell.value = 'WO'
    cell.data_type = s

Saving to samples/formula_test_output.xlsx...

--------------------------------------------------------------------------------
STEP 4: Reopen saved workbook with data_only=False
--------------------------------------------------------------------------------

Cell M13 after save and reopen:
  data_only=False mode:
    cell.value = 'WO'
    cell.data_type = s

--------------------------------------------------------------------------------
STEP 5: Reopen saved workbook with data_only=True
--------------------------------------------------------------------------------

Cell M13 after save and reopen:
  data_only=True mode:
    cell.value = 'WO'
    cell.data_type = s

--------------------------------------------------------------------------------
STEP 6: Test modifying a cell then saving
--------------------------------------------------------------------------------

Before modification:
    cell.value = 'WO'

After setting cell.value = 'A':
    cell.value = 'A'
    cell.data_type = s

Saved to samples/formula_test_modified.xlsx

--------------------------------------------------------------------------------
STEP 7: Verify modified cell after reopen
--------------------------------------------------------------------------------

Cell M13 after modification and reopen:
  data_only=False mode:
    cell.value = 'A'
    cell.data_type = s
```

---

## Analysis

### What Happens When Loading with data_only=True

**In Memory**:
1. openpyxl reads cached values from the Excel file
2. Formula definitions are NOT loaded into memory
3. `cell.value` returns the evaluated result
4. `cell.data_type` changes from `'f'` to `'s'`

**On Save**:
1. openpyxl writes current cell values to file
2. Since formulas were never loaded, they cannot be written back
3. All formula cells become static value cells
4. Formula definitions are permanently lost

### Why This Happens

openpyxl cannot store both formulas and values simultaneously:

- `data_only=False`: Stores formulas, values not available
- `data_only=True`: Stores values, formulas not loaded

This is a fundamental limitation of openpyxl's design. It cannot round-trip formulas when using `data_only=True`.

---

## Impact on Attenist

### Current Behavior

```
Load with data_only=False (default):
  - cell.value = '=F13' (formula string)
  - Marking attendance: overwrites '=F13' with 'A'
  - Save: writes 'A' to cell
  - Formula replaced by design (attendance marking)
```

### Behavior with data_only=True Fix

```
Load with data_only=True:
  - cell.value = 'WO' (evaluated value)
  - Marking attendance: overwrites 'WO' with 'A'
  - Save: writes 'A' to cell
  - Formula never existed in memory
```

**Result**: Same end state for attendance cells, but different read behavior.

---

## Workbook Analysis

### Formulas Found in Sample Workbook

From the JUN 26 Terrier MDR 2026 REGISTER.xlsx:

**Attendance Formula Cells**: 30 cells
- Formulas like: `=F13`, `=G12`, `=H8`, etc.
- These reference other cells in the same row
- All evaluate to valid shift codes: 'A', 'B', 'C', 'G', 'WO'

**Purpose**: Copy shift values from one column to another (likely schedule template)

**Error Values**: 6 cells
- Value: `#N/A`
- Likely from failed VLOOKUP or similar

**Other Observations**:
- 1,838 cells have direct values (no formulas)
- Formulas only in ~1.6% of attendance cells

---

## Risk Assessment

### Low Risk Scenario

**If workbooks are used only for attendance tracking**:
- Formulas are likely template artifacts
- Marking attendance overwrites them anyway
- Users don't need formula logic after marking
- Losing formulas is acceptable

### High Risk Scenario

**If workbooks have complex formula dependencies**:
- Other sheets may reference these cells
- Formulas may update dynamically based on other inputs
- Users may rely on formula behavior
- Losing formulas breaks workbook functionality

### Unknown

Without understanding the user's workflow:
- Cannot determine if formula preservation is required
- Need user input on acceptable tradeoffs
- May need to support both use cases

---

## Alternative Solutions

### Option 1: Accept Formula Loss (Simple)

**Implementation**:
```python
# workbook/loader.py
def load(self, path: str):
    return load_workbook(path, data_only=True)
```

**Pros**:
- Simple one-line change
- Fixes audit log issue
- Reads correct values

**Cons**:
- Destroys formulas on save
- May break complex workbooks
- Irreversible data loss

**Appropriate if**:
- Attendance marking always overwrites cells
- No formula dependencies exist
- Users accept formula loss

---

### Option 2: Dual Workbook Loading

**Implementation**:
```python
class AttendanceService:
    def __init__(self, workbook_path):
        self.workbook_path = workbook_path
        # Load for reading values
        self.workbook_values = load_workbook(workbook_path, data_only=True)
        # Load for writing/saving
        self.workbook_formulas = load_workbook(workbook_path, data_only=False)
    
    def get_cell_value(self, sheet_name, row, col):
        # Read from data_only=True workbook
        return self.workbook_values[sheet_name].cell(row, col).value
    
    def set_cell_value(self, sheet_name, row, col, value):
        # Write to data_only=False workbook
        self.workbook_formulas[sheet_name].cell(row, col).value = value
        # Sync to values workbook (optional)
        self.workbook_values[sheet_name].cell(row, col).value = value
    
    def save(self):
        # Save the formula-preserving workbook
        self.workbook_formulas.save(self.workbook_path)
```

**Pros**:
- Reads correct values
- Preserves unmodified formulas
- No data loss

**Cons**:
- Higher memory usage (2x workbook objects)
- More complex implementation
- Need to keep both in sync

**Appropriate if**:
- Formula preservation is required
- Some cells should keep formulas
- Users need formula behavior

---

### Option 3: Read-Only Evaluation

**Implementation**:
```python
class AttendanceService:
    def get_cell_value(self, cell):
        if cell.data_type == 'f':
            # Formula cell - manually resolve reference
            formula = cell.value
            if formula.startswith('='):
                ref = formula[1:]  # Remove '='
                # Parse cell reference (simplified)
                col_letter = ''.join(c for c in ref if c.isalpha())
                row_num = ''.join(c for c in ref if c.isdigit())
                # Get referenced cell
                ref_col = ord(col_letter.upper()) - ord('A') + 1
                ref_row = int(row_num)
                ref_cell = cell.parent.cell(row=ref_row, column=ref_col)
                return ref_cell.value
        return cell.value
```

**Pros**:
- Preserves formulas
- Reads correct values
- No memory overhead

**Cons**:
- Complex formula parsing needed
- Only handles simple references (=A1)
- Doesn't work with complex formulas
- Brittle implementation

**Appropriate if**:
- Only simple cell references exist
- Formula patterns are predictable
- Limited formula complexity

---

### Option 4: Conditional Loading

**Implementation**:
```python
class WorkbookLoader:
    def load(self, path: str, data_only=False):
        return load_workbook(path, data_only=data_only)

# In UI
class MainWindow:
    def __init__(self, workbook_path):
        # Check if workbook has formulas
        # If yes, prompt user for mode
        # If no, use data_only=True
```

**Pros**:
- User control over behavior
- Flexible for different use cases
- Can warn about data loss

**Cons**:
- More UI complexity
- User may not understand implications
- Still need to choose default behavior

**Appropriate if**:
- Mixed use cases exist
- Users can make informed choices
- Different workflows need different behavior

---

## Test Artifacts

### Created Test Files

1. `samples/formula_test_output.xlsx`
   - Workbook saved after loading with data_only=True
   - Contains static values instead of formulas

2. `samples/formula_test_modified.xlsx`
   - Workbook with modified cell value
   - Cell M13 changed from 'WO' to 'A'

### Test Script

- `test_formula_preservation.py`
  - Reproduces the formula preservation issue
  - Tests all scenarios
  - Documents behavior

---

## Conclusions

### Proven Facts

1. **Loading with data_only=True reads correct values**: ✓
   - Cell M13 returns 'WO' instead of '=F13'

2. **Saving after data_only=True destroys formulas**: ✓
   - Formula '=F13' replaced with static 'WO'

3. **Modifying cells works correctly**: ✓
   - New values are saved properly

4. **Formula loss is irreversible**: ✓
   - Once saved, formulas cannot be recovered

### Decision Points

**Must determine**:

1. Do users need formula preservation?
   - If NO: Use data_only=True (Option 1)
   - If YES: Use dual workbook or conditional loading (Options 2 or 4)

2. What is the nature of these formulas?
   - Template artifacts: Safe to destroy
   - Active dependencies: Must preserve

3. What is the user's expectation?
   - Marking attendance should replace formulas: data_only=True acceptable
   - Workbooks should remain dynamic: Need preservation solution

### Recommendation

**Before implementing any fix**:

1. Ask users about formula requirements
2. Document expected behavior
3. Consider making data_only configurable
4. Test with real user workbooks
5. Provide user warning if formulas will be lost

**For Attenist specifically**:

Given that:
- Attendance marking overwrites cells by design
- Formulas are only in 1.6% of cells
- No evidence of complex formula dependencies

**The simple fix (Option 1) is likely acceptable**, but should be:
- Documented as breaking change
- Tested with real workflows
- Possibly made configurable

---

## Implementation Guidance

### If Choosing Option 1 (data_only=True)

```python
# workbook/loader.py
def load(self, path: str):
    workbook_path = Path(path)
    
    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Workbook not found: {workbook_path}"
        )
    
    # WARNING: This will destroy formulas on save
    # Formulas will be replaced with evaluated values
    return load_workbook(workbook_path, data_only=True)
```

**Update README or documentation**:
```
NOTE: Attenist evaluates cell formulas when loading workbooks.
If your workbook contains formulas, they will be converted to
static values when you save. This is necessary for accurate
attendance tracking and audit logging.
```

### If Choosing Option 2 (Dual Workbook)

Requires refactoring AttendanceService to maintain both workbook objects and sync changes between them. More complex but safer.

### If Choosing Option 4 (User Choice)

Add UI prompt:
```
This workbook contains formulas. Attenist can:
1. Preserve formulas (slower, more memory)
2. Convert to values (faster, formulas will be lost)

Choose based on your workflow needs.
```

---

## Test Cleanup

To remove test artifacts:
```bash
rm samples/formula_test_output.xlsx
rm samples/formula_test_modified.xlsx
rm test_formula_preservation.py
```
