from core.models import Employee


class EmployeeIndexer:
    def build(self, workbook):
        employees = []

        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                serial = row[0].value
                emp_id = row[1].value
                name = row[2].value
                rank = row[3].value

                if (
                    serial is None
                    or emp_id is None
                    or name is None
                ):
                    continue

                if not isinstance(serial, int):
                    continue

                employee = Employee(
                    employee_id=str(emp_id).strip(),
                    name=str(name).strip(),
                    rank=str(rank).strip()
                    if rank
                    else "",
                    sheet_name=sheet.title,
                    row=row[0].row,
                )

                employees.append(employee)

        return employees