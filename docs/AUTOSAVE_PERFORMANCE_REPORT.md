# AUTOSAVE_PERFORMANCE_REPORT.md

## 1. FILES MODIFIED
*   **`ui/main_window.py`**:
    *   Added `self.unsaved_changes` and `self.last_save_time` state tracking.
    *   Implemented `QTimer` for background autosave checks.
    *   Added `status_label` and `manual_save_button` to the GUI.
    *   Refactored `mark_attendance` for instantaneous in-memory updates.
    *   Implemented `perform_save()` to handle disk I/O, backup, and atomic swap.
    *   Implemented `closeEvent()` for data loss prevention on exit.

## 2. PREVIOUS WORKFLOW
1.  Mark Attendance.
2.  Workbook writes to disk (1-3 seconds).
3.  Backup creation (0.5 seconds).
4.  Atomic file swap (0.1 seconds).
5.  Success popup appears (requires operator click).
6.  UI returns to ready state.
*Total latency: ~2-4 seconds per employee.*

## 3. NEW WORKFLOW
1.  Mark Attendance.
2.  Workbook object updated in memory (<0.01 seconds).
3.  Audit log updated.
4.  Dirty counter increments.
5.  UI immediately returns to ready state.
*Total latency: <0.01 seconds per employee (Instant).*

## 4. AUTOSAVE LOGIC
The application protects data integrity without blocking the operator through two triggers:
*   **Trigger A (Volume)**: Automatically saves to disk after every **20** unsaved changes.
*   **Trigger B (Time)**: A background timer checks every 5 seconds; if **60 seconds** have passed since the last save and changes exist, it triggers a save.

## 5. EXIT PROTECTION LOGIC
If the operator attempts to close the window with unsaved changes, a dialog appears:
*   **Save**: Commits changes to disk and exits.
*   **Discard**: Exits immediately without saving.
*   **Cancel**: Returns to the application.

## 6. ESTIMATED SPEED IMPROVEMENT
*   **Previous**: ~20-30 employees per minute (limited by disk I/O and popups).
*   **New**: ~100-200+ employees per minute (limited only by operator typing speed).
*   **Latency Reduction**: **>99%** improvement in per-mark responsiveness.

## 7. MANUAL TESTING PROCEDURE
1.  Open a workbook.
2.  Mark 5 employees in rapid succession.
    - *Expected*: UI stays responsive, "Unsaved Changes" counter increments, no "Success" popups.
3.  Wait 60 seconds.
    - *Expected*: Counter resets to 0, audit log shows "AUTOSAVE: Triggered by timeout".
4.  Mark 20 employees.
    - *Expected*: Counter resets to 0 automatically upon reaching 20.
5.  Mark 1 employee and click "Save Workbook".
    - *Expected*: Manual save commits change immediately.
6.  Mark 1 employee and close the app.
    - *Expected*: Warning dialog appears.
