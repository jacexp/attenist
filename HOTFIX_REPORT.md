# HOTFIX_REPORT.md

## 1. ROOT CAUSE
The application was crashing on Windows startup due to an `AttributeError`. The `eventFilter` implementation in `ui/main_window.py` was attempting to access `PySide6.QtCore.Qt.KeyPress`. In PySide6, event types are categorized under `QEvent.Type`, not the general `Qt` namespace.

## 2. FILES MODIFIED
*   **`ui/main_window.py`**:
    *   Added `from PySide6.QtCore import QEvent` to imports.
    *   Refactored `eventFilter` to use `QEvent.Type.KeyPress` for event type comparison.

## 3. EXACT FIX APPLIED

### Import Fix:
```python
# Old
from PySide6.QtCore import Qt
# New
from PySide6.QtCore import Qt, QEvent
```

### Event Comparison Fix:
```python
# Old
if watched == self.shift_combo and event.type() == Qt.KeyPress:
# New
if watched == self.shift_combo and event.type() == QEvent.Type.KeyPress:
```

## 4. VALIDATION PERFORMED
*   **Startup Verification**: Confirmed that the application launches without the `AttributeError`.
*   **Functional Verification**: Verified that pressing `Enter` while the Shift dropdown has focus correctly triggers the `mark_attendance()` method.
*   **Cross-Platform Check**: The use of `QEvent.Type.KeyPress` is the standard PySide6/Qt6 way and is fully compatible with both Windows and Linux environments.
*   **Stability Sweep**: Reviewed other PySide6 enums (e.g., `Qt.Key_Return`, `Qt.WindowModal`). These are used correctly as they are either available in the top-level `Qt` namespace or properly aliased in PySide6.

## 5. REMAINING KNOWN ISSUES
*   **Python Version**: The project still specifies `requires-python = ">=3.14"`. While not a blocker for the logic fix, this should be adjusted in the repository configuration to match available stable versions (e.g., 3.12).
