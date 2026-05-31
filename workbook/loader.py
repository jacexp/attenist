from pathlib import Path

from openpyxl import load_workbook


class WorkbookLoader:
    def load(self, path: str):
        workbook_path = Path(path)

        if not workbook_path.exists():
            raise FileNotFoundError(
                f"Workbook not found: {workbook_path}"
            )

        return load_workbook(workbook_path)