class AttendanceWriter:
    def mark(
        self,
        sheet,
        row: int,
        column: int,
        shift: str,
    ):
        sheet.cell(
            row=row,
            column=column,
            value=shift,
        )