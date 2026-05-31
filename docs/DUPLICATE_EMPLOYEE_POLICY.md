# DUPLICATE_EMPLOYEE_POLICY.md

**Policy:**
The Attenist application shall treat **Employee ID** as a primary identifier but acknowledges that **Worksheet Boundaries** define the data entry scope.

1.  **Collision Handling**: The `EmployeeIndexer` will scan all worksheets. If an `employee_id` appears on multiple sheets, all instances shall be indexed as distinct `Employee` records.
2.  **Data Structure**: Internal indexes will transition from ID-to-Employee maps to collections that support multiple entries (e.g., Lists or Multi-maps) to prevent silent data loss during indexing.
3.  **Search Result Disambiguation**: The `SearchService` must return all matching `Employee` records. The UI will be updated to display the **Worksheet Name** alongside the Employee name to ensure the operator selects the correct context.
4.  **Routing Integrity**: Attendance writing is strictly bound to the `sheet_name` and `row` stored within the `Employee` object, ensuring no "cross-sheet" writing errors.

**Rationale:**
- **Zero Data Loss**: Ensures no row in the Excel workbook is ignored due to an ID collision.
- **Audit Accuracy**: Maintains a 1:1 mapping between the operator's selection and the physical Excel cell.
- **Operational Safety**: Protects against common Excel "copy-paste" errors where duplicate IDs might exist across different departments.
