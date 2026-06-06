# Workbook-Only Architecture

## Overview

The Excel workbook (.xlsx) is now the **single source of truth** for employee data. SQLite is no longer used for OCR matching, verification, search, or attendance operations.

## New Architecture

```
Workbook (.xlsx)
    ↓
EmployeeIndexer.build()
    ↓
List[Employee] (in-memory)
    ↓
WorkbookService (index)
    ↓
┌─────────────────────────────────────┐
│  OCR ValidationService              │
│  SearchService                      │
│  EmployeeSearchDialog               │
│  VerificationWizard                 │
└─────────────────────────────────────┘
    ↓
Attendance Updates (write back to workbook)
```

## Components

### New Components

| Component | File | Purpose |
|-----------|------|---------|
| `WorkbookService` | `services/workbook_service.py` | In-memory employee index with search/lookup methods |

### Modified Components

| Component | File | Change |
|-----------|------|--------|
| `OCRValidationService` | `services/ocr/validation_service.py` | Uses `WorkbookService` instead of `DatabaseService` |
| `SearchService` | `services/search_service.py` | Uses `WorkbookService` instead of `DatabaseService` |
| `OCRAttendanceTab` | `ui/ocr_attendance_tab.py` | Accepts `WorkbookService` instead of `DatabaseService` |
| `MainWindow` | `ui/main_window.py` | Creates `WorkbookService` from employee list |
| `main.py` | `main.py` | Removed database sync stages |

### Deprecated Components (Legacy)

| Component | File | Status |
|-----------|------|--------|
| `DatabaseService` | `database/database_service.py` | Legacy - kept for Employee Management tab only |
| `EmployeeRepository` | `database/employee_repository.py` | Legacy - not used by search/OCR |
| Employee sync logic | `main.py` | Removed from startup |

## Performance Impact

| Metric | Before (SQLite) | After (In-Memory) |
|--------|-----------------|-------------------|
| Search latency | ~5-50ms (disk I/O) | ~0.1-1ms (memory) |
| Startup time | +2-5s (sync) | Immediate |
| Memory usage | Low | +5-20MB (depends on employee count) |
| Data consistency | Sync issues possible | Always consistent |

## Memory Impact

- 394 employees ≈ ~200KB memory
- 1000 employees ≈ ~500KB memory
- Index overhead: ~2x employee count (for `_by_id` and `_by_sheet` dictionaries)

## Verification Results

| Test | Status |
|------|--------|
| OCR Match (exact ID lookup) | ✓ Passed |
| Change Match (search by ID) | ✓ Passed |
| Manual Correction (search by name) | ✓ Passed |
| Employee Search (all sheets mode) | ✓ Passed |
| Active-sheet filtering | ✓ Passed |
| Case-insensitive search | ✓ Passed |
| Attendance commit (row mapping) | ✓ Passed |
| SearchService integration | ✓ Passed |

## WorkbookService API

```python
class WorkbookService:
    def __init__(self, employees: List[Employee]):
        """Build in-memory index from employee list."""

    def get_employee_by_id(self, emp_id: str) -> Optional[Dict]:
        """Get employee by ID. Returns dict for backward compatibility."""

    def get_employee_as_object(self, emp_id: str) -> Optional[Employee]:
        """Get employee as Employee object."""

    def search_employees(self, query: str, limit: int = 50,
                         sheet_name: Optional[str] = None) -> List[Dict]:
        """Search employees by name or ID, optionally filtered by sheet."""

    def search_employees_as_objects(self, query: str, limit: int = 50,
                                   sheet_name: Optional[str] = None) -> List[Employee]:
        """Search employees and return as Employee objects."""

    def get_employees_by_sheet(self, sheet_name: str) -> List[Dict]:
        """Get all employees from a specific sheet."""

    def get_employees_by_sheet_as_objects(self, sheet_name: str) -> List[Employee]:
        """Get all employees from a sheet as Employee objects."""

    def get_all_employees(self, limit: int = 1000) -> List[Dict]:
        """Get all employees."""

    def get_all_sheets(self) -> List[str]:
        """Get list of all sheet names."""

    def get_employee_count(self) -> int:
        """Get total employee count."""
```

## Migration Notes

1. **No database required**: The application now works without SQLite for search/OCR operations
2. **Backward compatibility**: `DatabaseService` is still available for the Employee Management tab (legacy)
3. **Data consistency**: Employee data is always read directly from the workbook
4. **Search improvements**: Case-insensitive sheet filtering, no sync delays
