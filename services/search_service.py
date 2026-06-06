from typing import Optional
from rapidfuzz import process, fuzz
from services.workbook_service import WorkbookService


class SearchService:
    def __init__(self, workbook_service: WorkbookService = None):
        """
        Initialize SearchService with workbook backend.

        Args:
            workbook_service: WorkbookService instance for in-memory search
        """
        self.workbook_service = workbook_service

    def search(self, query: str, limit: int = 10,
               sheet_name: Optional[str] = None):
        """
        Search employees using workbook index.
        Returns results in format [{"employee": Employee, "score": int}].
        """
        if not self.workbook_service:
            return []

        query = query.strip()
        if not query:
            return []

        employee_objects = self.workbook_service.search_employees_as_objects(
            query, limit * 2, sheet_name=sheet_name
        )

        results = []
        query_upper = query.upper()

        for emp in employee_objects:
            emp_id_upper = emp.employee_id.upper()
            emp_name_upper = emp.name.upper()

            if query_upper == emp_id_upper or query_upper == emp_name_upper:
                score = 100
            elif emp_id_upper.startswith(query_upper):
                score = 95
            elif emp_name_upper.startswith(query_upper):
                score = 95
            elif query_upper in emp_id_upper:
                score = 85
            elif query_upper in emp_name_upper:
                score = 85
            else:
                id_ratio = fuzz.ratio(emp_id_upper, query_upper)
                name_ratio = fuzz.partial_ratio(emp_name_upper, query_upper)
                score = max(id_ratio, name_ratio)

            if score >= 10:
                results.append({"employee": emp, "score": score})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
