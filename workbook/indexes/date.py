import datetime

class DateIndexer:
    DATE_ROW = 5

    def build(self, sheet):
        dates = {}

        for col in range(1, sheet.max_column + 1):
            value = sheet.cell(
                row=self.DATE_ROW,
                column=col,
            ).value

            if value is None:
                continue

            day = None
            if isinstance(value, int):
                day = value
            elif isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
                day = value.day
            elif isinstance(value, str):
                try:
                    # Handle cases like "01", "02" or "1.0"
                    day = int(float(value))
                except (ValueError, TypeError):
                    pass

            if day is not None and 1 <= day <= 31:
                dates[day] = col

        return dates