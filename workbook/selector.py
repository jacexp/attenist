class WorksheetSelector:
    def get_sheet_names(self, workbook):
        return workbook.sheetnames

    def select(self, workbook, sheet_name: str):
        if sheet_name not in workbook.sheetnames:
            raise ValueError(
                f"Worksheet '{sheet_name}' not found"
            )

        return workbook[sheet_name]