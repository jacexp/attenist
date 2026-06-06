# Attenist V2.0 – SQLite Migration Architecture

## Current State

- Excel workbook is the primary source of attendance data.
- Employee search functionality currently relies on indexing data directly from Excel workbooks.
- Attendance marking operations continue to write directly to Excel workbooks.
- Investigation into formula handling within Excel cells is complete, confirming that values derived from formulas (e.g., `=F13`) are read as the formula string itself, not its evaluated result, in audit logs.
- The formula interpretation issue is recognized as a known limitation for V1, and no further fixes will be implemented for this specific behavior in the context of this migration.

## Goal

The primary goal for Attenist V2.0 is to replace the existing Excel-based employee indexing and management with a robust SQLite database solution, while strictly maintaining Excel as the authoritative ledger for attendance records.

## Requirements

1.  **Automatic Database Creation:** The SQLite database (`employees.db`) must be created automatically upon application startup if it does not already exist, without requiring manual intervention.
2.  **First Workbook Load Synchronization:**
    *   If `employees.db` is missing, it must be created.
    *   All unique employee records (Employee ID, Name, Department, Designation) must be extracted from the loaded Excel workbook.
    *   The extracted employee data must automatically populate the newly created or existing SQLite database.
3.  **SQLite-based Employee Search:** All employee search functionalities within the application must query the SQLite database instead of directly indexing from Excel.
4.  **Preservation of Excel Attendance Writes:** Attendance marking and modification operations must continue to write directly to the Excel workbooks, as Excel remains the attendance ledger.
5.  **Future OCR System Integration:** The SQLite database design must be forward-compatible to support future Optical Character Recognition (OCR) system requirements, specifically for querying employee information.
6.  **In-Application Employee Management:** The application must provide a dedicated module for managing employee records (Add, Edit, Delete, Search) directly within its user interface.

## A. Database Schema

The SQLite database will consist of the following tables, designed for efficiency, data integrity, and future extensibility.

**Table: `employees`**
Stores core employee information.

| Column Name      | Data Type | Constraints                                    | Description                                     |
| :--------------- | :-------- | :--------------------------------------------- | :---------------------------------------------- |
| `id`             | TEXT      | PRIMARY KEY, NOT NULL                          | Unique Employee ID (from Excel)                 |
| `name`           | TEXT      | NOT NULL                                       | Full Name of the Employee                       |
| `department`     | TEXT      |                                                | Employee's Department                           |
| `designation`    | TEXT      |                                                | Employee's Job Designation                      |
| `excel_row`      | INTEGER   |                                                | Original row number in Excel (for reference)    |
| `last_sync_date` | TEXT      |                                                | Timestamp of the last successful sync from Excel |

**Indexes:**
- `CREATE INDEX idx_employee_name ON employees (name);`
- `CREATE INDEX idx_employee_department ON employees (department);`
- `CREATE INDEX idx_employee_designation ON employees (designation);`

**Table: `metadata`**
Stores application-specific metadata, such as database version or last successful sync time.

| Column Name | Data Type | Constraints    | Description                         |
| :---------- | :-------- | :------------- | :---------------------------------- |
| `key`       | TEXT      | PRIMARY KEY, NOT NULL | Metadata key (e.g., 'db_version')   |
| `value`     | TEXT      |                | Associated value for the metadata key |

**Table: `ocr_aliases` (Future OCR Support)**
Designed to store aliases or alternative names for employees, which can be matched by an OCR system. This table provides a flexible way to associate multiple textual representations with a single canonical employee record without altering the core `employees` table.

| Column Name | Data Type | Constraints                               | Description                                         |
| :---------- | :-------- | :---------------------------------------- | :-------------------------------------------------- |
| `id`        | INTEGER   | PRIMARY KEY AUTOINCREMENT                 | Unique ID for the alias record                      |
| `employee_id` | TEXT    | NOT NULL, FOREIGN KEY (`employee_id`) REFERENCES `employees`(`id`) ON DELETE CASCADE | Foreign key linking to the `employees` table      |
| `alias_name` | TEXT      | NOT NULL                                  | An alternative name or spelling for the employee    |
| `confidence` | REAL      | CHECK (`confidence` >= 0.0 AND `confidence` <= 1.0) | Optional: OCR confidence score for this alias (0.0 to 1.0) |

**Indexes:**
- `CREATE INDEX idx_ocr_aliases_employee_id ON ocr_aliases (employee_id);`
- `CREATE INDEX idx_ocr_aliases_alias_name ON ocr_aliases (alias_name);`

## B. Startup Flow

The application's startup flow will be redesigned to incorporate the SQLite database validation and synchronization process.

1.  **Open Workbook:** The user selects and opens an Excel attendance workbook.
2.  **Initialize Database Connection:** The application attempts to establish a connection to `employees.db` in the application's root directory.
3.  **Validate DB / Create DB if Missing:**
    *   If `employees.db` does not exist, it is automatically created.
    *   The necessary tables (`employees`, `metadata`, `ocr_aliases`) are created with their defined schemas.
    *   The `metadata` table is populated with initial values (e.g., `db_version`).
4.  **Sync Employees from Workbook:**
    *   The application extracts all employee data (ID, Name, Department, Designation) from the currently loaded Excel workbook.
    *   This data is then used to synchronize the `employees` table in the SQLite database. (Details in Section C).
5.  **Build Search Index (in-memory cache for UI):** While the primary search will query SQLite, for rapid UI responsiveness, a lightweight, in-memory cache of employee IDs and names might be built from the SQLite database. This is distinct from the deprecated Excel index.
6.  **Launch UI:** The main application user interface is launched, with employee search functionalities now backed by SQLite.

## C. Employee Synchronization

Synchronization will occur on every workbook load, ensuring the SQLite `employees` table reflects the most current state of employees in the *currently loaded* Excel workbook. This approach prioritizes Excel as the source of truth for employee existence and core attributes, while allowing the SQLite database to be the active employee master for the application's functionality.

**Synchronization Logic:**

1.  **Extract Workbook Data:** Read all employee records (ID, Name, Department, Designation) from the loaded Excel workbook.
2.  **Fetch Database Data:** Retrieve all existing employee records from the SQLite `employees` table.
3.  **Process Changes:**
    *   **New Employee in Workbook:** If an employee ID exists in the workbook but not in the database, insert the new employee record into the `employees` table.
    *   **Removed Employee (from Workbook perspective):** If an employee ID exists in the database but not in the current workbook, the employee record is marked for *inactivation* or *soft deletion* by updating a `status` column (e.g., 'active' / 'inactive') in the `employees` table. This prevents immediate hard deletion, preserving historical context. (Alternatively, if hard deletion is acceptable, the record can be deleted.)
    *   **Edited Employee:** If an employee ID exists in both the workbook and the database, compare their `name`, `department`, and `designation`. If any attribute differs, update the corresponding record in the `employees` table with the values from the workbook. Update `last_sync_date`.
    *   **Duplicate IDs in Workbook:** The system will identify duplicate employee IDs within the *same* Excel workbook during extraction. Only the *first occurrence* of a duplicate ID will be processed for synchronization; subsequent duplicates will be logged as warnings and ignored to maintain data integrity in SQLite.
4.  **Conflict Handling:** In cases of conflicting data (e.g., an employee's name manually edited in the SQLite Employee Management module vs. a different name for the same ID in the Excel workbook), the Excel workbook data *always takes precedence* during synchronization. Any manual changes made via the Employee Management UI will be overwritten if the corresponding Excel data differs. This ensures Excel remains the ultimate source of truth for core employee details.

## D. Employee Management Module

A dedicated UI tab/module will be implemented within the application to allow in-application management of employee records stored in SQLite.

**Module Design:**

*   **Main Display Area:**
    *   A table/list view displaying all employee records from the `employees` table in SQLite.
    *   Columns: Employee ID, Name, Department, Designation, Last Sync Date.
    *   Clickable rows to select an employee for editing/deletion.

*   **Search Bar:**
    *   An input field for real-time searching of employees.
    *   Searches by: Employee ID, Name, Department, Designation (fuzzy matching encouraged).
    *   Results update dynamically in the main display area.

*   **Action Buttons:**
    *   **"Add Employee" Button:**
        *   Action: Opens a modal dialog or navigates to a form for entering new employee details (ID, Name, Department, Designation).
        *   Validation: Ensures Employee ID is unique.
        *   Upon submission, the new employee is added to the SQLite database.
        *   **Note on Conflict:** Manually added employees are *not* automatically synced to Excel. If an Excel workbook is loaded later with the same Employee ID but different details, the Excel data will overwrite the manually added data in SQLite during sync. This reinforces Excel as the master for core attributes.
    *   **"Edit Employee" Button (Active when an employee is selected):**
        *   Action: Opens a modal dialog/form pre-populated with the selected employee's details.
        *   Allows modification of Name, Department, Designation. Employee ID is immutable.
        *   Upon submission, updates the record in the SQLite database.
        *   **Note on Conflict:** Similar to "Add," manual edits may be overwritten by Excel during subsequent syncs if the data in Excel differs.
    *   **"Delete Employee" Button (Active when an employee is selected):**
        *   Action: Prompts for confirmation.
        *   Upon confirmation, performs a *soft deletion* by updating a `status` column (e.g., 'inactive') in the `employees` table. This preserves referential integrity for any future linked data (e.g., OCR logs). Hard deletion should be an advanced, rarely used feature, if at all.
        *   **Note on Conflict:** If an employee marked 'inactive' in SQLite reappears in a loaded Excel workbook, their status will be reverted to 'active' during the next sync.
    *   **"Refresh from Workbook" Button:**
        *   Action: Triggers an immediate re-synchronization process between the currently loaded Excel workbook and the SQLite database, identical to the startup sync logic. This allows users to explicitly update the employee master from Excel.

## E. Search Migration

The employee search mechanism will undergo a significant migration from direct Excel indexing to querying the SQLite database.

**Current (Excel Index) Data Flow:**

1.  **Search Input:** User enters search query in UI.
2.  **Excel Index:** Application queries an in-memory index built by parsing the active Excel workbook.
3.  **Results:** Matching employee names/IDs from the Excel index are displayed.

**New (SQLite) Data Flow:**

1.  **Search Input:** User enters search query in UI.
2.  **SQLite Query:** The application executes a SQL query against the `employees` table in `employees.db`. The query will typically use `LIKE` clauses for fuzzy matching on `name`, `id`, `department`, or `designation`.
    *   Example Query: `SELECT id, name FROM employees WHERE name LIKE '%search_term%' OR id LIKE '%search_term%';`
3.  **Employee Object Creation:** The results from SQLite are mapped to Employee objects within the application.
4.  **Attendance Write to Excel (Unchanged):** Once an employee is identified via the SQLite search, any attendance marking operations *still write directly to the active Excel workbook* at the appropriate cell. The SQLite database is *not* involved in modifying attendance data.

## F. Service Architecture

The new architecture introduces a clear separation of concerns, organized into new and existing modules.

**Module: `database/`**
*   **`employee_db.py`:**
    *   **Responsibility:** Handles all direct interactions with the `employees.db` SQLite file.
    *   **Functions:**
        *   `initialize_database()`: Creates `employees.db` and tables if they don't exist.
        *   `insert_employee(employee_data)`: Adds a new employee record.
        *   `update_employee(employee_id, new_data)`: Modifies an existing employee record.
        *   `delete_employee(employee_id)`: Marks an employee as inactive (soft delete).
        *   `get_employee_by_id(employee_id)`: Retrieves a single employee record.
        *   `get_all_employees()`: Retrieves all employee records.
        *   `search_employees(query_string)`: Performs filtered searches on employee data.
        *   `sync_employees_from_excel(excel_data)`: Manages the synchronization logic.
        *   `add_ocr_alias(employee_id, alias_name, confidence)` (Future): Adds an OCR alias.

**Module: `services/`**
*   **`employee_service.py` (New):**
    *   **Responsibility:** Provides business logic for employee-related operations, acting as an intermediary between the UI and the `employee_db.py`.
    *   **Functions:**
        *   `load_employees_from_excel(workbook_path)`: Extracts employee data from Excel.
        *   `perform_initial_sync(excel_data)`: Orchestrates the first-time database population and subsequent syncs.
        *   `get_search_results(query)`: Calls `employee_db.search_employees` and formats results for UI.
        *   `add_employee_record(data)`: Validates and adds employees via `employee_db`.
        *   `edit_employee_record(id, data)`: Validates and edits employees via `employee_db`.
        *   `remove_employee_record(id)`: Handles soft deletion via `employee_db`.
        *   `refresh_employee_data_from_excel(workbook_path)`: Triggers a full resync.
*   **`attendance_service.py` (Existing, modified):**
    *   **Responsibility:** Continues to manage attendance-related operations, but now interacts with `employee_service.py` for employee lookups.
    *   **Modifications:** Update employee lookup logic to use `employee_service.get_search_results` instead of direct Excel indexing.

**Module: `ui/`**
*   **`employee_management_tab.py` (New):**
    *   **Responsibility:** Implements the user interface for the Employee Management Module.
    *   **Components:**
        *   Search bar widget.
        *   Table/list view widget for displaying employees.
        *   Buttons: Add, Edit, Delete, Refresh from Workbook.
        *   Dialogs/forms for Add/Edit operations.
    *   **Interactions:** Communicates with `employee_service.py` for all data operations.
*   **`main_window.py` (Existing, modified):**
    *   **Responsibility:** Integrates the new `employee_management_tab.py` as a new tab in the main application window.
    *   **Modifications:** Add a new tab for "Employee Management."
    *   Ensure proper initialization of `employee_service` and passing it to relevant UI components.

## G. OCR Readiness

The database schema has been designed with future OCR integration in mind, specifically through the `ocr_aliases` table and the extensible nature of the `employees` table.

1.  **Match Employee IDs:** The `id` column in the `employees` table serves as the canonical employee identifier. OCR output for IDs can directly query this column for exact matches.
2.  **Match Employee Names / Aliases:**
    *   OCR systems often produce slightly varied readings of names. The `ocr_aliases` table directly addresses this by allowing multiple `alias_name` entries to be associated with a single `employee_id`.
    *   When OCR processes an employee name, it can query the `ocr_aliases` table (or the `name` column in `employees`) for matches.
    *   The `alias_name` can store common misspellings, abbreviations, or variations found by OCR.
3.  **Store Aliases:** The `ocr_aliases` table explicitly provides a mechanism to store these alternative names without polluting the core `employees` table. This allows for a clean separation of canonical data from OCR-specific matching data.
4.  **Store OCR Confidence:** The `confidence` column in `ocr_aliases` allows the future OCR system to store a numerical confidence score (e.g., 0.0 to 1.0) for each alias. This can be used by the application to rank or prioritize OCR matches, or to flag low-confidence readings for manual review. This is crucial for robust OCR error handling.
5.  **No Schema Redesign Required:** The `ocr_aliases` table can be populated and utilized by the OCR system without requiring any structural changes to the `employees` or `metadata` tables, thus fulfilling the requirement for future-proofing.

## H. Risks and Mitigation

**1. Sync Risks**

*   **Risk:** Data inconsistencies between Excel and SQLite due to partial syncs or errors during the synchronization process.
*   **Mitigation:**
    *   **Atomic Transactions:** Ensure synchronization operations are wrapped in SQLite transactions. If any part of the sync fails, the entire transaction is rolled back, preventing partial updates.
    *   **Logging:** Implement comprehensive logging for the synchronization process, detailing insertions, updates, and (soft) deletions, as well as any skipped duplicate IDs.
    *   **Clear Precedence:** Explicitly document and enforce that Excel data always takes precedence during sync, overwriting manual SQLite edits to core employee attributes.
    *   **User Feedback:** Provide clear UI feedback to the user regarding sync status and any detected discrepancies or warnings (e.g., duplicate IDs in Excel).

**2. Corruption Risks**

*   **Risk:** Corruption of the `employees.db` file, leading to data loss or application crashes.
*   **Mitigation:**
    *   **WAL Mode:** Configure SQLite to use Write-Ahead Logging (WAL) mode. This improves concurrency and robustness against crashes.
    *   **Regular Backups:** While not automated by Attenist, inform users about the importance of regularly backing up the `employees.db` file, especially before major application updates.
    *   **Error Handling:** Implement robust `try-except` blocks around all database operations to catch and handle SQLite errors gracefully, preventing application termination.
    *   **Schema Versioning:** Use the `metadata` table to store a `db_version`. This allows for controlled schema migrations in future updates if table structures need to change.

**3. Duplicate Risks**

*   **Risk:** Introduction of duplicate employee IDs in the SQLite database if Excel data is inconsistent or due to race conditions.
*   **Mitigation:**
    *   **Primary Key Constraint:** The `id` column in the `employees` table is defined as `PRIMARY KEY`, automatically preventing duplicate IDs in the database at the schema level.
    *   **Workbook Pre-processing:** During Excel data extraction, implement a check to detect and log duplicate IDs *within the workbook itself* before attempting to insert them into SQLite. Only the first unique instance should be processed.
    *   **Synchronization Logic:** The sync logic (Section C) explicitly handles new, updated, and removed employees based on unique IDs, ensuring duplicates are not created.

**4. Performance Risks**

*   **Risk:** Slow performance during large Excel workbook loads (due to sync) or during employee search operations.
*   **Mitigation:**
    *   **Batch Operations:** For large-scale insertions/updates during sync, use SQLite's `executemany` method to perform operations in batches, significantly reducing overhead compared to single-row inserts.
    *   **Indexing:** All frequently queried columns (`name`, `department`, `designation`, `alias_name`) have appropriate indexes (`idx_employee_name`, `idx_employee_department`, `idx_employee_designation`, `idx_ocr_aliases_employee_id`, `idx_ocr_aliases_alias_name`). This drastically speeds up search queries.
    *   **Optimized Queries:** Ensure SQL queries are well-written and avoid full table scans where indexes can be utilized.
    *   **Asynchronous Operations:** Consider performing the initial sync in a background thread or asynchronously, especially for very large workbooks, to prevent blocking the UI during application startup. Provide a progress indicator to the user.
    *   **In-Memory Cache:** For highly interactive UI elements (like the search bar in the Employee Management Module), consider maintaining a small, in-memory cache of frequently accessed employee data (e.g., ID and Name) derived from SQLite. This can provide near-instantaneous search results for common queries, with the full SQLite search as a fallback.
