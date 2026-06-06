# Database Migration Fix Report

## Root Cause Analysis

The application encountered a `sqlite3.OperationalError: no such column: sheet_name` upon startup. 

**Analysis:**
- The `Employee` model was updated to include `sheet_name` and `row_number` to support multi-sheet Excel workbooks.
- The `EmployeeRepository` expected these columns to exist in the SQLite database.
- Existing `employees.db` files created by earlier versions of the application only contained the base columns (`emp_id`, `emp_name`, `rank`, `created_at`, `updated_at`).
- When the application tried to access or index `sheet_name` in an old database, SQLite threw an operational error because the column did not exist.

## Migration Strategy

To resolve this without requiring users to delete their existing `employees.db` (preserving manual employee entries), a dynamic schema migration system was implemented.

### 1. Base Schema Definition
The `_create_tables` method was refactored to only create the "base" schema (columns that have always existed). This ensures that the table creation process never fails, regardless of the database version.

### 2. Dynamic Column Detection
The `_migrate_schema` method now uses `PRAGMA table_info(employees)` to inspect the actual columns present in the database at runtime.

### 3. Incremental Upgrades
If required columns are missing, the system applies `ALTER TABLE employees ADD COLUMN ...` commands. This allows the database to be upgraded incrementally from any previous version to the current one.

### 4. Index Rebuilding
Indices that depend on migrated columns (e.g., `idx_emp_sheet`) are created *after* the columns have been successfully added, preventing "no such column" errors during index creation.

## Schema Versioning Approach

The system now utilizes a `metadata` table to track the state of the database.

- **Version Tracking**: A key `schema_version` is stored in the `metadata` table.
- **Current Version**: The latest version is marked as `2.0`.
- **Automatic Updates**: Whenever a migration is applied, the version is updated to reflect the current state.
- **Idempotency**: Migration logic is idempotent; it checks for the existence of columns before attempting to add them, making it safe to run on every application startup.

## Files Modified

| File Path | Change Description |
| :--- | :--- |
| `database/employee_repository.py` | Implemented `_migrate_schema`, `_update_schema_version`, and refactored `_ensure_database_exists` and `_create_tables`. |

## Verification Results

**Pre-Fix State:**
- Columns: `['emp_id', 'emp_name', 'rank', 'created_at', 'updated_at']`
- Result: Startup Crash (`OperationalError: no such column: sheet_name`)

**Post-Fix State:**
- Columns: `['emp_id', 'emp_name', 'rank', 'created_at', 'updated_at', 'sheet_name', 'row_number', 'synced_from_excel']`
- Result: Successful startup, existing data preserved, new columns added automatically.

**Verification Command:**
```python
from database.employee_repository import EmployeeRepository
repo = EmployeeRepository('employees.db')
# Result: Success
```

## Conclusion

The database is now self-healing. Both fresh installations and legacy databases are automatically brought to the correct schema version upon startup, ensuring stability and data continuity for all users.
