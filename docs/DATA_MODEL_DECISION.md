# DATA MODEL DECISION

## ANALYSIS OF MODELS

### OPTION A: Single Attendance Sheet Model
Assumption: All employees exist on a single worksheet.

1. **Advantages:**
   - Simplest possible indexing logic (loop one sheet).
   - `AttendanceService` only requires a single sheet reference.
   - Minimal memory overhead.
2. **Disadvantages:**
   - Extremely brittle. If an organization grows and HR splits the workbook into tabs (e.g., "Guards", "Operators") to bypass Excel row limits or for visual clarity, the app immediately fails.
   - Fails the core requirement: The prompt stated, "The workbook is structured into multiple sections (Security Officers, Female Guards, Male Guards, ID Operators, CCTV Operators, etc.) but the operator should not need to care about sections." If these sections map to sheets, Option A guarantees immediate failure.
3. **Complexity impact:** Low.
4. **Maintenance impact:** High when HR inevitably changes the workbook format.
5. **Risk level:** CRITICAL. It violates stated business reality.
6. **Effect on architecture:** Keeps the current rigid `MainWindow` structure.

### OPTION B: Multiple Attendance Sheets Model
Assumption: Employees are distributed across multiple worksheets, and updates must be routed.

1. **Advantages:**
   - Highly resilient. Aligns with real-world Excel usage where data is categorized into tabs.
   - Fulfils the "operator should not care" requirement.
2. **Disadvantages:**
   - Requires slightly more complex indexing logic (iterating `workbook.worksheets`).
   - `Employee` model must track `sheet_name`.
   - `AttendanceService` must dynamically lookup the worksheet object on every write.
3. **Complexity impact:** Medium.
4. **Maintenance impact:** Low. It gracefully handles workbook expansion.
5. **Risk level:** Low. It is the defensive programming choice.
6. **Effect on architecture:** `EmployeeIndexer` becomes a global indexer. `AttendanceService` requires a reference to the `workbook` object, not just a single `sheet`.

---

## MODEL DESIGN RESOLUTION

The stated project constraints explicitly declare: *"The workbook is structured into multiple sections... but the operator should not need to care about sections."*

In Excel, "sections" almost always manifest as distinct Worksheets (tabs), or at worst, disjointed tables on a single massive sheet. To build a robust system, the architecture must support the most complex, realistic scenario: **Employees distributed across multiple Worksheets.**

### The Employee Model

The `Employee` model must contain sufficient routing information so that when the operator clicks "Mark", the application knows exactly where that data lives in the source file.

```python
@dataclass(slots=True)
class Employee:
    employee_id: str
    name: str
    rank: str
    sheet_name: str  # Critical for routing
    row: int
```

### Application Workflow Strategy

**Decision:** B) Automatically index all worksheets and hide worksheet details from the operator.

**Rationale:** Daily operators are optimized for speed, not configuration. Forcing them to select "Sheet: Female Guards", then search "Jane Doe", only to realize she was moved to "ID Operators", destroys productivity. The system must act as a global, unified search facade over the fragmented Excel data structure.

---

## FINAL ARCHITECTURE STRATEGY

### 1. FINAL DATA MODEL
*   **`Employee`**: Tracks `employee_id`, `name`, `rank`, `sheet_name`, `row`.
*   **`WorkbookContext`** (Implicit or Explicit): The application holds the `OpenPyXL` workbook object in memory. It no longer holds a single "active sheet" pointer.

### 2. FINAL INDEXING STRATEGY
*   **Global Indexing:** Upon workbook load, the `EmployeeIndexer` iterates through `workbook.sheetnames`.
*   **Heuristic Scanning:** For each sheet, it scans for valid employee rows (e.g., checking if Column A is a serial number and Column B is an ID).
*   **Unified Map:** It returns a unified dictionary mapping: `employee_id -> Employee`.
*   **Date Indexing Assumption:** We assume the date columns (1-31) are uniform across all valid sheets. If Sheet A has dates on row 5, and Sheet B has them on row 5, the `DateIndexer` only needs to run once on the first valid sheet found, or we maintain a mapping of `sheet_name -> {day: column}` if structural drift is expected. For simplicity and based on current code, a single uniform date map is assumed, but we will index dates per-sheet if necessary.

### 3. FINAL SEARCH STRATEGY
*   **Global Search:** The `SearchService` operates entirely on the unified memory index.
*   **Disambiguation:** It must return a `List[Employee]`.
*   **No Dict Collisions:** Internal representations will ensure exact same names are kept in a `List` rather than overwriting dict keys.

### 4. FINAL ATTENDANCE WRITING STRATEGY
*   **Dynamic Resolution:** The `AttendanceService.mark(employee, day, shift)` method no longer relies on a pre-selected sheet.
*   **Action:**
    1. Extract `sheet_name` and `row` from the `Employee` object.
    2. Extract `column` from the `DateIndexer` mapping.
    3. Retrieve the target worksheet: `sheet = self.workbook[employee.sheet_name]`.
    4. Mutate `sheet.cell(row, column)`.
    5. Log the action locally.
    6. (Optionally) mark the workbook as "dirty" for deferred atomic saving.

This architecture decouples the operator's mental model (a single unified workforce) from the reality of the storage format (fragmented Excel sheets), ensuring speed, accuracy, and long-term maintainability.
