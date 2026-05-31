# MULTI_SHEET_IMPLEMENTATION_PLAN.md

## GOAL
Implement multi-sheet support with minimal code changes. The application will index all employees across all worksheets and route attendance marks to the correct sheet automatically.

## FILES TO CHANGE

### 1. `core/models.py`
*   **Change**: Add `sheet_name: str` to the `Employee` dataclass.
*   **Responsibility**: Define the data structure for a routable employee.

### 2. `workbook/indexes/employee.py`
*   **Change**: Modify `build()` to iterate through `sheet.parent.worksheets` (or take the `workbook` as an argument).
*   **Responsibility**: Scan all sheets in the workbook and populate the `sheet_name` for every `Employee` instance.

### 3. `services/attendance_service.py`
*   **Change**: 
    *   Accept the `workbook` instead of a specific `sheet` in `__init__`.
    *   In `mark()`, resolve the specific sheet using `self.workbook[employee.sheet_name]`.
*   **Responsibility**: Route cell mutations to the correct worksheet based on the employee's metadata.

### 4. `ui/main_window.py`
*   **Change**:
    *   Remove `WorksheetSelector`.
    *   Update `EmployeeIndexer().build()` call to pass the workbook or trigger multi-sheet indexing.
    *   Update `AttendanceService` initialization to pass the workbook object.
*   **Responsibility**: Initialize the system for global scope instead of single-sheet scope.

## DATA FLOW
1.  **Load**: `WorkbookLoader` returns a `workbook`.
2.  **Index**: `EmployeeIndexer` loops through all sheets in `workbook`, creating `Employee(..., sheet_name="...")` objects.
3.  **Search**: `SearchService` works as before (it doesn't care about `sheet_name`).
4.  **Mark**: 
    *   Operator selects `Employee`.
    *   `AttendanceService` looks up `workbook[employee.sheet_name]`.
    *   `AttendanceService` writes to the specific row on that sheet.

## RISKS
*   **Performance**: Iterating through 20+ sheets with thousands of rows might cause a 1-3 second lag on startup (UI freeze).
*   **Data Overlap**: If an employee ID exists on two different sheets, the last one scanned will overwrite the first in the dictionary.
*   **Header Variations**: If one sheet has headers on row 5 and another on row 10, the indexer will fail to find employees on the non-standard sheet.

## MIGRATION & BACKWARD COMPATIBILITY
*   **Model Compatibility**: Adding `sheet_name` is backward compatible as long as the indexer populates it.
*   **Single-Sheet Fallback**: If a workbook only has one sheet, the logic remains identical (it just loops once).
*   **Minimal Invasiveness**: We are not changing the search algorithm or the UI layout, only the "plumbing" of how rows are found and written to.

## SUCCESS CRITERIA
1.  Open a workbook with two sheets: "Security" and "Guards".
2.  Search for an employee in "Guards" and mark them.
3.  Verify the Excel file reflects the change on the "Guards" tab.
4.  Search for an employee in "Security" and mark them.
5.  Verify the Excel file reflects the change on the "Security" tab.
