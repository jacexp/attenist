class DateIndexer:
    DATE_ROW = 5

    def build(self, sheet):
        dates = {}

        for col in range(1, sheet.max_column + 1):
            value = sheet.cell(
                row=self.DATE_ROW,
                column=col,
            ).value

            if isinstance(value, int):
                dates[value] = col

        return dates