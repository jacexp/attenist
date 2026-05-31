# SAVE_FEEDBACK_REPORT.md

## 1. FILES MODIFIED
*   **`ui/main_window.py`**:
    *   Imported `QProgressDialog`, `QApplication`, and `Qt`.
    *   Added `set_ui_enabled(bool)` helper method to toggle all input controls.
    *   Refactored `perform_save()` to include synchronous UI feedback and locking.

## 2. RECENT ENHANCEMENTS

### UI Locking & Feedback
When a save operation (Manual or Autosave) begins, the application now:
1.  **Disables all input controls**: Prevents the operator from typing or clicking while the UI is frozen during disk I/O.
2.  **Shows a Progress Dialog**: Displays a modal "Saving workbook..." dialog to inform the user that a background task is in progress.
3.  **Updates Status Label**: Sets the status to "Saving workbook..." for immediate feedback.
4.  **Forces UI Update**: Uses `QApplication.processEvents()` to ensure the dialog and label are rendered before the blocking `attendance_service.save()` call begins.

### Post-Save Success Indicators
Once the save is successful:
1.  **Status Update**: Shows "Save complete (Unsaved: 0)" in green.
2.  **Re-enables UI**: Restores all controls for immediate follow-up entry.
3.  **Closes Dialog**: Automatically closes the progress dialog.

## 3. RISKS MITIGATED
*   **Operator Confusion**: Previously, the 1-3 second freeze during autosave could make the app appear "crashed". The progress dialog now provides a clear reason for the temporary lack of responsiveness.
*   **Race Conditions/Input Loss**: By disabling the UI during saving, we prevent the operator from entering data that might be processed incorrectly or lost during the I/O block.

## 4. MANUAL TEST PROCEDURE
1.  Open a workbook.
2.  Mark 20 employees to trigger an **Autosave**.
    - *Expected*: All inputs gray out, a "Saving workbook..." dialog appears for ~1-2 seconds, then disappears. Status text turns green.
3.  Mark 1 employee and click **Save Workbook**.
    - *Expected*: Same visual feedback as the autosave.
4.  Open the Excel file in another app to create a lock, then click **Save Workbook** in Attenist.
    - *Expected*: UI locks, dialog appears, then an error message appears. UI unlocks and status shows "Save FAILED" in red.

## 5. REMAINING KNOWN LIMITATIONS
*   **Blocking Main Thread**: Because the save happens on the UI thread (as per requirements to avoid architectural redesign), the progress dialog's spinner may not animate during the heaviest part of the Excel XML generation. However, the dialog remains visible and the UI remains locked, fulfilling the primary usability requirement.
