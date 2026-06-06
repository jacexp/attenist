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

    def _get_evaluated_value(self, cell):
        """Get evaluated value for formula cells, otherwise return cell.value."""
        if cell.data_type == 'f' and isinstance(cell.value, str) and cell.value.startswith('='):
            formula = cell.value[1:]
            ref_col = 0
            ref_row = 0
            
            for char in formula:
                if char.isalpha():
                    ref_col = ref_col * 26 + (ord(char.upper()) - ord('A') + 1)
                elif char.isdigit():
                    ref_row = ref_row * 10 + int(char)
            
            if ref_col > 0 and ref_row > 0:
                ref_cell = cell.parent.cell(row=ref_row, column=ref_col)
                if ref_cell.data_type == 'f' and isinstance(ref_cell.value, str) and ref_cell.value.startswith('='):
                    return self._get_evaluated_value(ref_cell)
                return ref_cell.value
        
        return cell.value

    def mark(
        self,
        employee,
        day,
        shift,
        active_sheet_name: str
    ):
        """
        Mark attendance for an employee on a specific day and shift.
        Includes safety check to ensure employee belongs to the active sheet.
        """
        # Safety Check: Ensure employee belongs to the selected sheet
        if employee.sheet_name != active_sheet_name:
            raise ValueError(
                f"Sheet mismatch! Employee {employee.employee_id} belongs to '{employee.sheet_name}', "
                f"but attempt made to write to '{active_sheet_name}'."
            )

        sheet = self.workbook[employee.sheet_name]

        column = self.dates[day]

        cell = sheet.cell(
            row=employee.row,
            column=column,
        )

        old_value = self._get_evaluated_value(cell)

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