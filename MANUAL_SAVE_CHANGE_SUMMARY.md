# MANUAL_SAVE_CHANGE_SUMMARY.md

## 1. FILES CHANGED
*   **`ui/main_window.py`**:
    *   Removed all autosave logic (timers and volume-based triggers).
    *   Implemented a new dual-panel layout (Entry Panel on left, Summary Panel on right).
    *   Added `summary_list` (QListWidget) to display pending changes in real-time.
    *   Added `Ctrl+S` keyboard shortcut via `QShortcut`.
    *   Updated `mark_attendance` to push changes to the summary panel and enable the save button.
    *   Updated `perform_save` to clear the summary panel and update the "Last Saved" timestamp.

## 2. PREVIOUS WORKFLOW
1.  Operator marks attendance.
2.  Application freezes for 1-3 seconds during disk I/O (either every mark or every 20 marks).
3.  Operator waits for the UI to become ready again.
4.  No visual record of what was just marked.

## 3. NEW WORKFLOW
1.  **Mark**: Operator marks attendance. Feedback is instantaneous (<0.01s).
2.  **Summary**: The marked employee and shift appear immediately in the "Pending Changes Summary" panel.
3.  **Continue**: Operator immediately searches for the next employee.
4.  **Save**: Operator presses **Ctrl+S** or clicks **Save Workbook** only when they are finished or want to take a break.
5.  **Review**: Changes are cleared from the summary panel only after a successful disk write.

## 4. HOW THE SUMMARY PANEL WORKS
The summary panel is a live `QListWidget`. Every time `mark_attendance` is called:
*   The workbook object is updated in memory.
*   A string like `Day 14: John Doe -> A (Security)` is appended to the list.
*   The list auto-scrolls to the bottom.
*   The "Unsaved Changes" counter increments.
*   The "Save Workbook" button is enabled.

## 5. HOW SAVE WORKS
The save operation is now strictly manual:
*   It performs a single, consolidated write of all in-memory changes.
*   It utilizes the existing safety features: **Pre-save backup** and **Atomic swap**.
*   It provides a "Saving..." progress dialog and locks the UI for the duration of the write.
*   On success, it clears the summary panel and updates the "Last Saved" timestamp.

## 6. MANUAL TEST PROCEDURE
1.  Open a workbook.
2.  Mark 3 employees in rapid succession.
    - *Expected*: No UI lag. The summary panel shows 3 items. The save button is enabled.
3.  Press **Ctrl+S**.
    - *Expected*: "Saving..." dialog appears. Summary panel clears. Save button disables. "Last Saved" timestamp updates.
4.  Mark 1 employee and try to close the app.
    - *Expected*: "Save before exit?" prompt appears.

## 7. EXPECTED OPERATOR BEHAVIOR
Operators are encouraged to enter data as fast as they can type. They should rely on the summary panel for a visual "sanity check" of their recent work and perform a manual save (Ctrl+S) at natural breaks in their workflow or at the end of their shift.
