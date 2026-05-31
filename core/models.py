from dataclasses import dataclass


@dataclass(slots=True)
class Employee:
    employee_id: str
    name: str
    rank: str
    sheet_name: str
    row: int


@dataclass(slots=True)
class AttendanceSession:
    workbook_path: str
    sheet_name: str
    attendance_day: int