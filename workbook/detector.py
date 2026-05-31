from openpyxl.worksheet.worksheet import Worksheet


class AttendanceTableDetector:
    KEYWORDS = {
        "ID NO",
        "EMP NAME",
    }

    def find_headers(self, sheet: Worksheet):
        matches = []

        for row in sheet.iter_rows():
            for cell in row:
                value = cell.value

                if value is None:
                    continue

                text = str(value).strip().upper()

                if text in self.KEYWORDS:
                    matches.append(
                        {
                            "row": cell.row,
                            "column": cell.column,
                            "value": text,
                        }
                    )

        return matches