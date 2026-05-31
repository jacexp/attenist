from dataclasses import dataclass


@dataclass(slots=True)
class WorkbookAnalysis:
    header_row: int
    date_row: int
    id_column: int
    name_column: int
    rank_column: int


class WorkbookAnalyzer:
    def analyze(self, sheet):
        return WorkbookAnalysis(
            header_row=4,
            date_row=5,
            id_column=2,
            name_column=3,
            rank_column=4,
        )