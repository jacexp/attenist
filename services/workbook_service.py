"""
Workbook Service - Single source of truth for employee data.
Uses in-memory index built from Excel workbook.
No SQLite dependency.
"""
import logging
from typing import List, Dict, Optional
from core.models import Employee
from rapidfuzz import fuzz


class WorkbookService:
    """Provides employee search/lookup using workbook as single source of truth."""

    def __init__(self, employees: List[Employee]):
        """
        Initialize with employee list from EmployeeIndexer.

        Args:
            employees: List of Employee objects built from workbook
        """
        self.employees = employees
        self._by_id: Dict[str, Employee] = {}
        self._by_sheet: Dict[str, List[Employee]] = {}
        self._build_index()

    def _build_index(self):
        """Build in-memory lookup indexes."""
        for emp in self.employees:
            eid = emp.employee_id.upper()
            self._by_id[eid] = emp

            sheet = emp.sheet_name or ""
            if sheet not in self._by_sheet:
                self._by_sheet[sheet] = []
            self._by_sheet[sheet].append(emp)

        logging.info(
            f"WorkbookService index built: "
            f"{len(self._by_id)} employees, "
            f"{len(self._by_sheet)} sheets"
        )

    def get_employee_by_id(self, emp_id: str) -> Optional[Dict]:
        """Get employee by ID. Returns dict for backward compatibility."""
        emp = self._by_id.get(emp_id.upper())
        if emp:
            return {
                "emp_id": emp.employee_id,
                "emp_name": emp.name,
                "rank": emp.rank,
                "sheet_name": emp.sheet_name,
                "row_number": emp.row,
            }
        return None

    def get_employee_as_object(self, emp_id: str) -> Optional[Employee]:
        """Get employee as Employee object."""
        return self._by_id.get(emp_id.upper())

    def search_employees(self, query: str, limit: int = 50,
                         sheet_name: Optional[str] = None) -> List[Dict]:
        """
        Search employees by name or ID, optionally filtered by sheet.
        Returns list of dicts for backward compatibility.
        """
        q = query.strip().upper()
        if not q:
            return []

        candidates = self._get_candidates(sheet_name)
        results = []

        for emp in candidates:
            eid = emp.employee_id.upper()
            name = emp.name.upper()

            if eid == q or name == q:
                score = 100
            elif eid.startswith(q) or name.startswith(q):
                score = 90
            elif q in eid or q in name:
                score = 80
            else:
                id_ratio = fuzz.ratio(eid, q)
                name_ratio = fuzz.partial_ratio(name, q)
                score = max(id_ratio, name_ratio)

            if score >= 10:
                results.append({
                    "emp_id": emp.employee_id,
                    "emp_name": emp.name,
                    "rank": emp.rank,
                    "sheet_name": emp.sheet_name,
                    "row_number": emp.row,
                    "_score": score,
                })

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:limit]

    def search_employees_as_objects(self, query: str, limit: int = 50,
                                   sheet_name: Optional[str] = None) -> List[Employee]:
        """Search employees and return as Employee objects."""
        results = self.search_employees(query, limit, sheet_name)
        objects = []
        for r in results:
            emp = self._by_id.get(r["emp_id"].upper())
            if emp:
                objects.append(emp)
        return objects

    def get_employees_by_sheet(self, sheet_name: str) -> List[Dict]:
        """Get all employees from a specific sheet as dicts."""
        emps = self._by_sheet.get(sheet_name, [])
        return [
            {
                "emp_id": emp.employee_id,
                "emp_name": emp.name,
                "rank": emp.rank,
                "sheet_name": emp.sheet_name,
                "row_number": emp.row,
            }
            for emp in emps
        ]

    def get_employees_by_sheet_as_objects(self, sheet_name: str) -> List[Employee]:
        """Get all employees from a sheet as Employee objects."""
        return self._by_sheet.get(sheet_name, [])

    def get_all_employees(self, limit: int = 1000) -> List[Dict]:
        """Get all employees as dicts."""
        return [
            {
                "emp_id": emp.employee_id,
                "emp_name": emp.name,
                "rank": emp.rank,
                "sheet_name": emp.sheet_name,
                "row_number": emp.row,
            }
            for emp in self.employees[:limit]
        ]

    def get_all_sheets(self) -> List[str]:
        """Get list of all sheet names."""
        return list(self._by_sheet.keys())

    def get_employee_count(self) -> int:
        """Get total employee count."""
        return len(self._by_id)

    def _get_candidates(self, sheet_name: Optional[str] = None) -> List[Employee]:
        """Get candidate employees filtered by sheet (case-insensitive)."""
        if sheet_name:
            upper_sheet = sheet_name.upper()
            return [
                emp for emp in self.employees
                if emp.sheet_name.upper() == upper_sheet
            ]
        return self.employees
