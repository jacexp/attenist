import re
import logging
from typing import List, Dict, Optional, Tuple
from enum import Enum
from rapidfuzz import process, fuzz
from database.database_service import DatabaseService
from core.models import Employee


class OCRStatus(Enum):
    CONFIRMED = "CONFIRMED"
    UNMATCHED = "UNMATCHED"
    UNREADABLE = "UNREADABLE"


class OCRValidationResult:
    def __init__(self, ocr_id: str, ocr_name: str, status: OCRStatus,
                 matched_employee: Optional[Employee] = None,
                 validation_notes: str = ""):
        self.ocr_id = ocr_id
        self.ocr_name = ocr_name
        self.status = status
        self.matched_employee = matched_employee
        self.validation_notes = validation_notes

        self.is_checked = status == OCRStatus.CONFIRMED
        self.checkbox_enabled = status == OCRStatus.CONFIRMED
        self.shift = ""

        self.manually_corrected = False
        self.original_ocr_id = ocr_id
        self.original_ocr_name = ocr_name

    def to_dict(self) -> Dict:
        return {
            'ocr_id': self.ocr_id,
            'ocr_name': self.ocr_name,
            'status': self.status.value,
            'matched_employee': {
                'employee_id': self.matched_employee.employee_id,
                'name': self.matched_employee.name,
                'rank': self.matched_employee.rank,
                'sheet_name': self.matched_employee.sheet_name,
                'row': self.matched_employee.row
            } if self.matched_employee else None,
            'validation_notes': self.validation_notes,
            'is_checked': self.is_checked,
            'checkbox_enabled': self.checkbox_enabled,
            'shift': self.shift,
            'manually_corrected': self.manually_corrected,
            'original_ocr_id': self.original_ocr_id,
            'original_ocr_name': self.original_ocr_name
        }


class OCRValidationService:
    def __init__(self, database_service: DatabaseService):
        self.database_service = database_service
        self.id_pattern = re.compile(r'^[A-Z]{1,4}\d{2,5}$')

        self.validation_stats = {
            'total_processed': 0,
            'confirmed': 0,
            'unmatched': 0,
            'unreadable': 0,
        }

    def validate_ocr_results(self, ocr_data: List[Dict], sheet_name: Optional[str] = None) -> List[OCRValidationResult]:
        validation_results = []
        self.validation_stats = {
            'total_processed': 0,
            'confirmed': 0,
            'unmatched': 0,
            'unreadable': 0,
        }

        for ocr_item in ocr_data:
            try:
                result = self._validate_single_result(ocr_item, sheet_name=sheet_name)
                validation_results.append(result)
                self.validation_stats['total_processed'] += 1
                self.validation_stats[result.status.value.lower()] += 1
            except Exception as e:
                logging.error(f"Failed to validate OCR item {ocr_item}: {e}")
                error_result = OCRValidationResult(
                    ocr_id=ocr_item.get('id', 'ERROR'),
                    ocr_name=ocr_item.get('name', 'ERROR'),
                    status=OCRStatus.UNREADABLE,
                    validation_notes=f"Validation error: {e}"
                )
                validation_results.append(error_result)
                self.validation_stats['total_processed'] += 1
                self.validation_stats['unreadable'] += 1

        return validation_results

    def _validate_single_result(self, ocr_item: Dict, sheet_name: Optional[str] = None) -> OCRValidationResult:
        ocr_id = ocr_item.get('id', '').strip().upper()
        ocr_name = ocr_item.get('name', '').strip().upper()

        if not self._is_valid_id_format(ocr_id):
            return OCRValidationResult(
                ocr_id=ocr_id,
                ocr_name=ocr_name,
                status=OCRStatus.UNREADABLE,
                validation_notes="Could not read a valid employee ID from this entry"
            )

        matched_employee = self._find_exact_match(ocr_id, sheet_name=sheet_name)

        if matched_employee:
            return OCRValidationResult(
                ocr_id=ocr_id,
                ocr_name=ocr_name,
                status=OCRStatus.CONFIRMED,
                matched_employee=matched_employee,
                validation_notes=f"Matched to {matched_employee.employee_id} - {matched_employee.name}"
            )
        else:
            return OCRValidationResult(
                ocr_id=ocr_id,
                ocr_name=ocr_name,
                status=OCRStatus.UNMATCHED,
                validation_notes="Valid ID format but no matching employee found in active sheet"
            )

    def _is_valid_id_format(self, emp_id: str) -> bool:
        return bool(self.id_pattern.match(emp_id))

    def _find_exact_match(self, emp_id: str, sheet_name: Optional[str] = None) -> Optional[Employee]:
        try:
            emp = self.database_service.get_employee_as_object(emp_id)
            if emp and sheet_name and emp.sheet_name != sheet_name:
                return None
            return emp
        except Exception as e:
            logging.error(f"Database lookup failed for {emp_id}: {e}")
            return None

    def find_possible_matches(self, ocr_id: str, ocr_name: str, sheet_name: str, limit: int = 5) -> List[Dict]:
        try:
            all_emps = self.database_service.search_employees_as_objects("", 500)
            sheet_emps = [e for e in all_emps if e.sheet_name == sheet_name]

            if not sheet_emps:
                return []

            scored = []
            for emp in sheet_emps:
                id_score = fuzz.ratio(ocr_id.upper(), emp.employee_id.upper())
                name_score = fuzz.partial_ratio(ocr_name.upper(), emp.name.upper()) if ocr_name else 0
                combined = max(id_score, name_score)
                if combined >= 40:
                    scored.append({"employee": emp, "score": combined})

            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:limit]

        except Exception as e:
            logging.error(f"find_possible_matches failed: {e}")
            return []

    def manual_correction(self, result: OCRValidationResult,
                          corrected_id: str = None,
                          selected_employee: Employee = None) -> OCRValidationResult:
        if corrected_id:
            corrected_item = {'id': corrected_id, 'name': result.ocr_name}
            corrected_result = self._validate_single_result(corrected_item)
            corrected_result.manually_corrected = True
            corrected_result.original_ocr_id = result.original_ocr_id
            corrected_result.original_ocr_name = result.original_ocr_name
            return corrected_result

        elif selected_employee:
            result.matched_employee = selected_employee
            result.status = OCRStatus.CONFIRMED
            result.validation_notes = "Manually matched employee"
            result.manually_corrected = True
            result.is_checked = True
            result.checkbox_enabled = True
            return result

        return result

    def search_employees_for_manual_match(self, query: str, sheet_name: Optional[str] = None, limit: int = 10) -> List[Employee]:
        try:
            results = self.database_service.search_employees_as_objects(query, limit * 3)
            if sheet_name:
                results = [e for e in results if e.sheet_name == sheet_name]
            return results[:limit]
        except Exception as e:
            logging.error(f"Employee search failed for query '{query}': {e}")
            return []

    def get_validation_statistics(self) -> Dict:
        return self.validation_stats.copy()

    def filter_ready_for_commit(self, results: List[OCRValidationResult]) -> List[OCRValidationResult]:
        ready_results = []
        for result in results:
            if (result.is_checked and
                result.status == OCRStatus.CONFIRMED and
                result.matched_employee):
                ready_results.append(result)
        return ready_results

    def validate_commit_readiness(self, results: List[OCRValidationResult]) -> Tuple[List[OCRValidationResult], List[str]]:
        ready_results = []
        warnings = []

        for result in results:
            if not result.is_checked:
                continue

            if result.status != OCRStatus.CONFIRMED:
                warnings.append(f"Row {result.ocr_id}: Status is {result.status.value}, not CONFIRMED")
                continue

            if not result.matched_employee:
                warnings.append(f"Row {result.ocr_id}: No matched employee")
                continue

            ready_results.append(result)

        return ready_results, warnings
