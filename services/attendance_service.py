import os
import re
import shutil
import logging
from pathlib import Path

logger = logging.getLogger("attendance_service")


class AttendanceService:
    def __init__(self, workbook, employees, dates):
        self.workbook = workbook
        self.employees = employees
        self.dates = dates
        self._backup_created = False

    # ── Formula Resolution ──────────────────────────────────────

    @staticmethod
    def _is_simple_reference(formula):
        """True if formula is a bare =A1 cell reference (no operators, functions, ranges)."""
        return bool(re.match(r'^=([A-Z]+)(\d+)$', formula.strip()))

    @staticmethod
    def _parse_simple_reference(formula):
        """Parse =A1 and return (column_number, row_number)."""
        match = re.match(r'^=([A-Z]+)(\d+)$', formula.strip())
        if not match:
            raise ValueError(f"Not a simple cell reference: {formula!r}")
        col_str = match.group(1)
        row = int(match.group(2))
        col = 0
        for ch in col_str:
            col = col * 26 + (ord(ch.upper()) - ord('A') + 1)
        return col, row

    def _resolve_formula_chain(self, cell, sheet, visited=None):
        """
        Recursively resolve a formula cell to its final non-formula source.

        Returns (source_cell, chain_list).

        Raises ValueError for:
          - Complex formulas (non-trivial =A1)
          - Circular references
          - Invalid/missing references
        """
        if visited is None:
            visited = set()

        cell_id = (cell.row, cell.column)
        if cell_id in visited:
            raise ValueError(
                f"Circular reference detected at {cell.column_letter}{cell.row}. "
                "Cannot resolve formula chain."
            )
        visited.add(cell_id)

        # Base case: not a formula cell
        if cell.data_type != 'f' or not isinstance(cell.value, str) or not cell.value.startswith('='):
            return cell, [cell]

        formula = cell.value

        if not self._is_simple_reference(formula):
            raise ValueError(
                f"Complex formula detected at {cell.column_letter}{cell.row}: {formula}. "
                "Only simple =A1 references are supported. Manual update required."
            )

        ref_col, ref_row = self._parse_simple_reference(formula)

        if ref_col < 1 or ref_row < 1:
            raise ValueError(
                f"Invalid reference in formula at {cell.column_letter}{cell.row}: {formula}"
            )

        try:
            ref_cell = sheet.cell(row=ref_row, column=ref_col)
        except Exception:
            raise ValueError(
                f"Invalid cell reference in formula at {cell.column_letter}{cell.row}: {formula}"
            )

        # Recurse if the referenced cell is also a formula
        if ref_cell.data_type == 'f' and isinstance(ref_cell.value, str) and ref_cell.value.startswith('='):
            source_cell, sub_chain = self._resolve_formula_chain(ref_cell, sheet, visited)
            return source_cell, [cell] + sub_chain

        # Terminal — non-formula cell
        return ref_cell, [cell, ref_cell]

    # ── Attendance Mark ─────────────────────────────────────────

    def mark(self, employee, day, shift, active_sheet_name: str):
        if employee.sheet_name != active_sheet_name:
            raise ValueError(
                f"Sheet mismatch! Employee {employee.employee_id} belongs to '{employee.sheet_name}', "
                f"but attempt made to write to '{active_sheet_name}'."
            )

        sheet = self.workbook[employee.sheet_name]
        
        # Determine column based on sheet-specific or global dates
        if isinstance(self.dates, dict) and any(isinstance(v, dict) for v in self.dates.values()):
            # Per-sheet date mapping
            sheet_dates = self.dates.get(employee.sheet_name, {})
            column = sheet_dates.get(day)
            
            if not column:
                # Fallback: check if any other sheet has this day indexed
                for s_name, s_dates in self.dates.items():
                    if day in s_dates:
                        column = s_dates[day]
                        logger.warning(f"Date {day} not found in sheet '{employee.sheet_name}', using column from '{s_name}'")
                        break
        else:
            # Simple global date mapping
            column = self.dates.get(day)

        if not column:
            raise KeyError(day)

        target_cell = sheet.cell(row=employee.row, column=column)

        # Determine write destination
        is_formula = (
            target_cell.data_type == 'f'
            and isinstance(target_cell.value, str)
            and target_cell.value.startswith('=')
        )

        if is_formula:
            source_cell, chain = self._resolve_formula_chain(target_cell, sheet)
            write_target = source_cell
            resolved_addr = f"{source_cell.column_letter}{source_cell.row}"
            chain_addrs = " -> ".join(
                f"{c.column_letter}{c.row}" for c in chain
            )
        else:
            write_target = target_cell
            resolved_addr = f"{target_cell.column_letter}{target_cell.row}"
            chain_addrs = resolved_addr

        old_value = write_target.value
        write_target.value = shift

        logger.info(
            f"WRITE TRACE: "
            f"Employee={employee.employee_id} "
            f"Name={employee.name} "
            f"Sheet={employee.sheet_name} "
            f"Target={target_cell.column_letter}{target_cell.row} "
            f"Chain={chain_addrs} "
            f"ResolvedSource={resolved_addr} "
            f"OldValue={old_value!r} "
            f"NewValue={shift!r}"
        )

        return old_value

    # ── Workbook Save ───────────────────────────────────────────

    def save(self, path):
        target_path = Path(path)

        if not self._backup_created and target_path.exists():
            backup_path = target_path.with_suffix(target_path.suffix + ".bak")
            shutil.copy2(target_path, backup_path)
            self._backup_created = True

        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")

        try:
            self.workbook.save(temp_path)
            os.replace(temp_path, target_path)
        except Exception:
            if temp_path.exists():
                os.remove(temp_path)
            raise
