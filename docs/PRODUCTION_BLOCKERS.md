# PRODUCTION_BLOCKERS.md

## 1. RUNTIME ERRORS / CRASHES

### A. `KeyError` on Attendance Marking (Critical)
*   **File**: `services/attendance_service.py`
*   **Line**: 23 (approx)
*   **Root Cause**: The `MainWindow` allows selecting any day from 1-31 via `day_combo`. However, `AttendanceService.mark` performs a direct lookup `self.dates[day]`. If the workbook only contains a partial month (e.g., days 1-15), selecting any other day will cause a `KeyError` and crash the application.
*   **Exact Fix**:
    ```python
    def mark(self, employee, day, shift):
        if day not in self.dates:
            raise KeyError(f"Day {day} not found in date index.")
        # ... rest of code
    ```
    And in `ui/main_window.py`:
    ```python
    def mark_attendance(self):
        # ...
        day = int(self.day_combo.currentText())
        if day not in self.dates:
            QMessageBox.warning(self, "Invalid Day", f"Day {day} is not available in this workbook.")
            return
        # ...
    ```

### B. `KeyError` on Default Day Initialization (High)
*   **File**: `ui/main_window.py`
*   **Line**: 68 (approx)
*   **Root Cause**: `self.day_combo.setCurrentText("14")` is hardcoded. If the operator marks attendance immediately without changing the day, and "14" is not in `self.dates`, the app crashes.
*   **Exact Fix**:
    ```python
    # Find the first available day in the index
    if self.dates:
        available_days = sorted(self.dates.keys())
        default_day = "14" if 14 in self.dates else str(available_days[0])
        self.day_combo.setCurrentText(default_day)
    ```

## 2. SIGNATURE & TYPE MISMATCHES

### A. Missing `WorksheetSelector` usage in `samples/test.py` (Functional)
*   **File**: `samples/test.py`
*   **Line**: 13-16
*   **Root Cause**: While `test.py` was updated, it still imports `WorksheetSelector` (unused) but more importantly, it doesn't verify if the `workbook` passed to `EmployeeIndexer` is valid before indexing.
*   **Exact Fix**: (Not a blocker, but a cleanup).

## 3. UNUSED CODE PATHS (Potential Confusion)

### A. `workbook/writer.py` (Total Dead Code)
*   **File**: `workbook/writer.py`
*   **Root Cause**: The entire file is obsolete. `AttendanceService` handles cell mutation directly. This file contains a `mark` method with an old signature that will crash if ever called.
*   **Exact Fix**: Delete `workbook/writer.py`.

### B. `workbook/selector.py` (Total Dead Code)
*   **File**: `workbook/selector.py`
*   **Root Cause**: The application now uses global indexing across all sheets. `WorksheetSelector` is no longer used or needed.
*   **Exact Fix**: Delete `workbook/selector.py`.

## 4. BROKEN IMPORTS

### A. `rapidfuzz` import in `services/search_service.py`
*   **File**: `services/search_service.py`
*   **Root Cause**: Ensure `process` and `fuzz` are available. (Checked `pyproject.toml`, they are listed).

## 5. TYPE MISMATCHES

### A. `results[0]` Assumption in `MainWindow`
*   **File**: `ui/main_window.py`
*   **Line**: 183 (approx)
*   **Root Cause**: `employee = results[0]["employee"]` assumes `results` is never empty.
*   **Exact Fix**: 
    ```python
    results = self.search_service.search(text)
    if not results:
        self.selected_employee = None
        self.match_label.setText("No match found")
        return
    ```
    (Currently handled in the updated `ui/main_window.py`, so this is safe).
