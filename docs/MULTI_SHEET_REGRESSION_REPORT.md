# MULTI_SHEET_REGRESSION_REPORT.md

## 1. CONFIRMED SAFE CHANGES

*   **Model Extension**: Adding `sheet_name` to the `Employee` dataclass is safe and does not affect existing field access.
*   **Search Engine**: The `SearchService` now correctly handles list-based indexing and supports duplicate names/IDs by returning lists of matches. This is a significant improvement over the previous dictionary-overwrite behavior.
*   **Attendance Routing**: `AttendanceService.mark` now correctly uses the `Employee` object's metadata to resolve the target worksheet, enabling cross-sheet writes.

## 2. CONFIRMED BREAKAGES

### A. `samples/test.py` (Critical Failure)
*   **Issue**: This script still attempts to pass a `sheet` to `EmployeeIndexer.build()` and expects a `dict` return. It then attempts a direct key lookup `employees["CC743"]`.
*   **Symptoms**: `TypeError` (passing sheet instead of workbook) followed by `TypeError` (subscripting a list with a string).
*   **Required Fix**: Update `test.py` to match the new global indexing and list-based search patterns.

### B. `ui/main_window.py` - Date Indexing (Brittle Logic)
*   **Issue**: `self.dates` is built using only `self.workbook.worksheets[0]`. 
*   **Symptoms**: If the first sheet in the workbook is an "Instructions" or "Summary" sheet without a date row, `self.dates` will be an empty dictionary. Subsequent attendance marks will crash with a `KeyError`.
*   **Required Fix**: Refactor `DateIndexer` or `MainWindow` to find the first sheet containing valid date columns.

## 3. SUSPECTED BREAKAGES & RISKS

### A. Search Disambiguation (UX Regression)
*   **Issue**: While `SearchService` now returns multiple matches for duplicate IDs/Names, the UI (`on_search_changed`) blindly selects `results[0]`.
*   **Risk**: An operator may inadvertently mark an employee in the wrong department if they share an ID/Name with someone else.
*   **Required Fix**: (Planned for Phase 2) Replace the label with a `QListWidget` to force manual selection when multiple matches exist.

### B. Dictionary Assumptions in `workbook/` logic
*   **Issue**: Any remaining code in `workbook/` that expects `EmployeeIndexer` to return a dictionary will fail.
*   **Audit Result**: `analyzer.py`, `detector.py`, and `schema.py` were not updated. If these files are active, they are likely broken. (Note: These files were marked for deletion in the Production Plan).

### C. `workbook/writer.py` (Signature Mismatch)
*   **Issue**: Contains a `mark` method with the old signature.
*   **Risk**: Low, as it appears unused by the current `AttendanceService`.
*   **Required Fix**: Delete the file as per the cleanup plan.

## 4. TEST CASES FOR VALIDATION

1.  **Empty First Sheet Test**: Load a workbook where the first tab is empty. Verify the app doesn't crash on startup and handles date indexing correctly.
2.  **Duplicate ID Test**: Search for an ID known to exist on two sheets. Verify both appear in the search logic (though currently only one in the UI).
3.  **Cross-Sheet Write Test**: Mark an employee on the 2nd sheet. Save and verify that the 1st sheet remains untouched and the 2nd sheet is correctly updated.
4.  **Special Characters in Sheet Names**: Test worksheets with spaces or symbols in their names to ensure `self.workbook[name]` resolution is stable.
