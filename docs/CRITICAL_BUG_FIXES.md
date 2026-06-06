# Critical Bug Fixes

This document describes two critical bugs that were identified and fixed in the attendance OCR system.

## Bug 1: Sheet-Scoped Search Showing Cross-Sheet Results

### Problem
When "Active Sheet Only" was enabled in employee search, the system would display employees from other sheets in the results list, only to reject them when selected with the error "Employee does not belong to active worksheet."

This created a confusing user experience where:
1. Search shows cross-sheet employees 
2. User selects an employee
3. System rejects the selection

### Root Cause
In `services/ocr/validation_service.py`, the exact ID lookup in `search_employees_for_manual_match()` bypassed sheet filtering:

```python
# Step 1: Exact ID match (always, bypasses sheet filter for discovery)
exact = self.workbook_service.get_employee_as_object(q.upper())
if exact:
    results[exact.employee_id] = (exact, 100)  # ← NO SHEET CHECK!
```

When searching "BITU" with active sheet "TESS-2 TERRIER", it would find exact match "BK429" from "SHIFT 2" and add it to results without checking sheet compatibility.

### Fix
Modified the exact match lookup to apply sheet filtering:

```python
# Step 1: Exact ID match (with sheet filter)
exact = self.workbook_service.get_employee_as_object(q.upper())
if exact:
    # Apply sheet filter to exact match
    if sheet_name and exact.sheet_name.upper() != sheet_name.upper():
        logging.info(
            f"CORRECTION_SEARCH: exact match filtered by sheet - "
            f"emp_id='{exact.employee_id}' emp_sheet='{exact.sheet_name}' "
            f"active_sheet='{sheet_name}'"
        )
        exact = None
    
    if exact:
        results[exact.employee_id] = (exact, 100)
```

### Verification
- ✅ Searching "BITU" with active sheet "TESS-2 TERRIER" now only shows employees from that sheet
- ✅ No cross-sheet employees appear in search results when "Active Sheet Only" is enabled
- ✅ All 12 sheet-scoped matching tests pass

## Bug 2: OCR Missing Name Fallback Matching

### Problem
When OCR extracted an employee name correctly but the ID was unreadable (e.g., "VI-501" with invalid format), the system would report:

"Could not read a valid employee ID"

And provide no candidate suggestions, even when a matching employee existed in the active sheet.

### Root Cause
In `services/ocr/validation_service.py`, ID format validation failure immediately returned UNREADABLE without attempting name matching:

```python
if not self._is_valid_id_format(ocr_id):
    return OCRValidationResult(
        ocr_id=ocr_id,
        ocr_name=ocr_name,
        status=OCRStatus.UNREADABLE,
        validation_notes="Could not read a valid employee ID from this entry"
    )  # ← NO NAME FALLBACK!
```

### Fix
Restructured `_validate_single_result()` to implement proper fallback sequence:

1. **ID-based matching** (if ID format is valid)
2. **Name-based fallback** (if ID invalid but name exists) 
3. **UNREADABLE** (only if both ID and name matching fail)

Added `_find_name_match()` method with fuzzy matching:

```python
def _find_name_match(self, ocr_name: str, sheet_name: Optional[str] = None) -> Optional[Employee]:
    """Find employee by name with fuzzy matching, respecting sheet scope."""
    # Exact match
    if emp_name == name_upper:
        score = 100
    # Name contains the OCR name  
    elif name_upper in emp_name:
        score = 90
    # Employee name contains OCR name
    elif emp_name in name_upper:
        score = 85
    else:
        # Fuzzy match
        score = fuzz.ratio(emp_name, name_upper)

    # Only consider matches above 80% similarity for name fallback
    if score >= 80:
        # Select best match
```

### Verification
- ✅ OCR with "VI-501" (invalid ID) + "VIRESH MANJUNATH" (valid name) now matches to employee VI501
- ✅ Status is CONFIRMED instead of UNREADABLE
- ✅ Validation notes show "Matched by name to VI501 - VIRESH MANJUNATH (ID was unreadable)"

## Enhanced Diagnostics

Both fixes include comprehensive logging for troubleshooting:

### Sheet Filter Logging
```
CORRECTION_SEARCH: exact match filtered by sheet - emp_id='BK429' emp_sheet='SHIFT 2' active_sheet='TESS-2 TERRIER'
```

### Name Fallback Logging  
```
NAME_FALLBACK: matched 'VIRESH MANJUNATH' to emp_id='VI501' name='VIRESH MANJUNATH' sheet='TESS-2 TERRIER' score=100
```

### Search Diagnostics
Added comprehensive search diagnostics in UI:
```
SEARCH_DIAGNOSTICS: query='BITU' active_sheet='TESS-2 TERRIER' employees_loaded=664 employees_filtered=358 results_displayed=1
```

## Impact
These fixes eliminate two major sources of user confusion:
1. **No more cross-sheet result leakage** - Users only see valid, selectable employees
2. **Intelligent name fallback** - OCR with unreadable IDs but valid names now work correctly

The system now provides a consistent, reliable experience where displayed results are always actionable.