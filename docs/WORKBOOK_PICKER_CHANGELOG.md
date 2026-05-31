# WORKBOOK_PICKER_CHANGELOG.md

## 1. FILES MODIFIED
*   **`main.py`**: Added `QFileDialog` logic to capture the workbook path before initializing the main window.
*   **`ui/main_window.py`**: Updated `__init__` to accept `workbook_path` and stored it as `self.workbook_path`. Updated the `save` call to use this path instead of a hardcoded string.

## 2. EXACT BEHAVIOR CHANGE
*   **Startup**: Instead of immediately opening with a hardcoded file, the application now presents a standard Windows/Linux file selection dialog titled "Open Attendance Workbook".
*   **Validation**: If the user cancels the dialog (clicks "Cancel" or "X"), the application terminates gracefully without error.
*   **Persistence**: The path selected at startup is remembered and used for all subsequent attendance "Save" operations, ensuring the user is always writing back to the file they opened.

## 3. MANUAL TEST PROCEDURE
1.  Run the application: `python main.py`.
2.  **Test Cancel**: Click "Cancel" on the file picker.
    - *Expected*: The app exits immediately.
3.  **Test Selection**: Re-run the app and select any `.xlsx` file (e.g., `samples/MAY_2026.xlsx`).
    - *Expected*: The app loads, indexes employees, and displays the main search interface.
4.  **Test Save**: Search for an employee, mark attendance, and click "Mark Attendance".
    - *Expected*: A "Success" message appears, and the changes are saved to the specific file selected in step 3.

## 4. EXPECTED RESULT
The application is no longer tied to a specific "samples" directory. It is now a generic tool that can be used to manage any attendance workbook in the correct format, regardless of its location on the filesystem.
