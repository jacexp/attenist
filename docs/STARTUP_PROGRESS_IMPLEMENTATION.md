# Startup Progress Dialog Implementation

## Files Changed

### Created: `ui/splash_dialog.py` (99 lines)
Non-blocking splash screen displayed during application initialization:
- **Title**: "Attenist v2" centered
- **Status label**: Shows current stage (e.g., "Building employee index...")
- **Workbook name label**: Hidden by default; shown when workbook loading begins (e.g., "Opening: test1.xlsx")
- **Progress bar**: 0-100%, text-less
- **Warning label**: Hidden by default; shown for non-critical issues (DB sync errors, missing API key)
- **Methods**:
  - `update(percent, status)` — advances progress bar and updates text
  - `set_workbook_name(name)` — shows workbook name
  - `show_warning(message)` — displays non-blocking orange warning
  - `show_ocr_warning(message)` — alias for `show_warning`
  - `close()` — safe to call multiple times

### Refactored: `main.py` (155 lines)
Loading split into 8 sequential stages with progress updates:

| Stage | % | Description |
|-------|---|-------------|
| 1 | 5% | Load configuration |
| 2 | 10% | Open workbook (PermissionError → abort) |
| 3 | 30% | Build employee index (heavy — scans all rows) |
| 4 | 45% | Build date index (scans row 5 of each sheet) |
| 5 | 60% | Connect SQLite database |
| 6 | 70% | Sync employees to database (errors → splash warning) |
| 7 | 85% | Check OCR API key (missing → splash warning) |
| 8 | 95% | Build MainWindow UI (lightweight — no I/O) |

Each stage calls `QApplication.processEvents()` to keep the splash responsive. If any stage throws an unhandled exception, the splash closes and a startup error dialog is shown.

### Refactored: `ui/main_window.py` (337 lines)
Constructor signature changed from:
```python
def __init__(self, workbook_path)
```
to:
```python
def __init__(self, workbook, employees, dates, database_service, workbook_path)
```

**Removed from `__init__`** (moved to `main.py`):
- `WorkbookLoader().load()` — workbook loading
- `EmployeeIndexer().build()` — employee index building
- `DatabaseService()` — database connection
- `_sync_employees_to_database()` — employee sync
- `FirstLaunchManager().check_and_configure()` — API key dialog (moved to OCR tab)

**Removed imports**: `WorkbookLoader`, `EmployeeIndexer`, `DateIndexer`, `DatabaseService`, `FirstLaunchManager`, `config`
**Removed method**: `_sync_employees_to_database()` (logic now in `main.py`)

**Kept unchanged**: `build_ui()`, `connect_signals()`, `setup_shortcuts()`, all mark/save/search logic, `closeEvent` handling.

## Key Design Decisions

1. **Splash after file dialog** — file selection can take arbitrary time (user browsing folders). Splash only appears for the actual loading phase.

2. **No QThread** — loading is sequential (stage 3 depends on stage 2, etc.), so `QApplication.processEvents()` between stages is sufficient. Thread would add complexity without benefit.

3. **Errors never block startup** — DB sync failure and missing API key show splash warnings instead of modal dialogs. Application always reaches MainWindow.

4. **OCR API key check deferred** — removed from startup entirely. OCR tab handles it when the user first clicks the OCR tab.

5. **Startup error handling** — outer `try/except` catches any unexpected crash during loading, closes splash, shows error dialog, and exits cleanly.
