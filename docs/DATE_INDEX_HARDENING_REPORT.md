# DATE_INDEX_HARDENING_REPORT.md

## 1. CHANGES SUMMARY

### FIX 1: Date Indexing Hardening (`ui/main_window.py`)
*   **Old Behavior**: The application blindly attempted to build the date index (mapping day numbers to Excel columns) using the very first sheet in the workbook (`workbook.worksheets[0]`). If the first sheet was a "Cover Page", "Instructions", or otherwise lacked attendance data, the application would have an empty date map and crash during attendance marking.
*   **New Behavior**: The application now iterates through all worksheets. It uses the `EmployeeIndexer` results to identify which sheets actually contain valid employee data. It attempts to build the date index from the first sheet that is confirmed to be a valid attendance section.
*   **Why**: To ensure the application is resilient to workbooks that contain non-data tabs (common in professional HR environments).

### FIX 2: Repair `samples/test.py`
*   **Old Behavior**: The script used outdated single-sheet logic, attempted to subscript a list as a dictionary, and used an obsolete `AttendanceService` signature.
*   **New Behavior**: Completely refactored to exercise the full multi-sheet lifecycle:
    1.  Loads a workbook via `WorkbookLoader`.
    2.  Performs global indexing across all sheets.
    3.  Uses the hardened date indexing logic.
    4.  Utilizes `SearchService` to find an employee.
    5.  Uses `AttendanceService` to mark attendance using the `Employee` object (routing to the correct sheet).
    6.  Saves the result.
*   **Why**: To provide a working diagnostic tool that accurately reflects the current production architecture.

## 2. TEST PROCEDURE

### Automated Test
Run the repaired test script:
```bash
python samples/test.py
```
**Expected Output**:
*   Should print "Found Employee: [Name] in [Sheet Name]".
*   Should print "Marking A for Day 15 on Row [Row]".
*   Should print "Saved to samples/test_output.xlsx".

### Manual UI Test
1.  Open Attenist.
2.  Observe if the application loads without a `QMessageBox` error.
3.  Search for an employee known to be on a non-first tab.
4.  Mark attendance.
5.  Verify success message and lack of crash.

## 3. EXPECTED BEHAVIOR
*   **Stability**: No crashes on workbooks with "dummy" first sheets.
*   **Accuracy**: Attendance is written to the correct sheet and correct day column, even in multi-sheet environments.
*   **Diagnostic**: `test.py` serves as a baseline for verifying the "plumbing" of the application without UI overhead.
