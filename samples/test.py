from workbook.loader import WorkbookLoader
from workbook.indexes.employee import EmployeeIndexer
from workbook.indexes.date import DateIndexer
from services.search_service import SearchService
from services.attendance_service import AttendanceService
from services.workbook_service import WorkbookService


def main():
    # 1. Load Workbook
    path = "samples/MAY_2026.xlsx"
    workbook = WorkbookLoader().load(path)

    # 2. Global Indexing
    employees = EmployeeIndexer().build(workbook)
    
    # 3. Date Indexing (Hardened)
    dates = {}
    for sheet in workbook.worksheets:
        if any(emp.sheet_name == sheet.title for emp in employees):
            dates = DateIndexer().build(sheet)
            if dates:
                break
    
    if not dates:
        print("Error: No valid dates found.")
        return

    # 4. Search Service
    workbook_service = WorkbookService(employees)
    search_service = SearchService(workbook_service)
    
    # 5. Attendance Service
    attendance_service = AttendanceService(workbook, employees, dates)

    # 6. Perform Search
    query = "CC743"
    results = search_service.search(query)
    
    if not results:
        print(f"No results for {query}")
        return

    employee = results[0]["employee"]
    day = 15
    shift = "A"

    print(f"Found Employee: {employee.name} in {employee.sheet_name}")
    print(f"Marking {shift} for Day {day} on Row {employee.row}")

    # 7. Mark Attendance (Routed)
    old_value = attendance_service.mark(
        employee,
        day,
        shift,
        active_sheet_name=employee.sheet_name
    )

    print(f"Previous Value: {old_value}")
    print(f"New Value: {shift}")

    # 8. Save (Routed)
    output_path = "samples/test_output.xlsx"
    attendance_service.save(output_path)

    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
