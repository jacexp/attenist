import os
import shutil
from pathlib import Path

class AttendanceService:
    def __init__(
        self,
        workbook,
        employees,
        dates,
    ):
        self.workbook = workbook
        self.employees = employees
        self.dates = dates
        self._backup_created = False

    def mark(
        self,
        employee,
        day,
        shift,
    ):
        sheet = self.workbook[employee.sheet_name]

        column = self.dates[day]

        cell = sheet.cell(
            row=employee.row,
            column=column,
        )

        old_value = cell.value

        cell.value = shift

        return old_value

    def save(self, path):
        target_path = Path(path)

        # Priority 3: Backup creation before first save
        if not self._backup_created and target_path.exists():
            backup_path = target_path.with_suffix(target_path.suffix + ".bak")
            shutil.copy2(target_path, backup_path)
            self._backup_created = True

        # Priority 4: Atomic save strategy
        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        
        try:
            self.workbook.save(temp_path)
            # Use os.replace for atomic swap on same partition
            os.replace(temp_path, target_path)
        except Exception:
            if temp_path.exists():
                os.remove(temp_path)
            raise