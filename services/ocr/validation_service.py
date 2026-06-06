import re
import logging
from typing import List, Dict, Optional, Tuple
from enum import Enum
from rapidfuzz import process, fuzz
from services.workbook_service import WorkbookService
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
    def __init__(self, workbook_service: WorkbookService):
        self.workbook_service = workbook_service
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

        # Try ID-based matching first if ID format is valid
        if self._is_valid_id_format(ocr_id):
            matched_employee = self._find_exact_match(ocr_id, sheet_name=sheet_name)
            if matched_employee:
                return OCRValidationResult(
                    ocr_id=ocr_id,
                    ocr_name=ocr_name,
                    status=OCRStatus.CONFIRMED,
                    matched_employee=matched_employee,
                    validation_notes=f"Matched by ID to {matched_employee.employee_id} - {matched_employee.name}"
                )
            else:
                return OCRValidationResult(
                    ocr_id=ocr_id,
                    ocr_name=ocr_name,
                    status=OCRStatus.UNMATCHED,
                    validation_notes="Valid ID format but no matching employee found in active sheet"
                )

        # ID format invalid - try name-based fallback matching if we have a name
        if ocr_name:
            name_match = self._find_name_match(ocr_name, sheet_name=sheet_name)
            if name_match:
                return OCRValidationResult(
                    ocr_id=ocr_id,
                    ocr_name=ocr_name,
                    status=OCRStatus.CONFIRMED,
                    matched_employee=name_match,
                    validation_notes=f"Matched by name to {name_match.employee_id} - {name_match.name} (ID was unreadable)"
                )

        # No valid ID and no name match - return unreadable
        return OCRValidationResult(
            ocr_id=ocr_id,
            ocr_name=ocr_name,
            status=OCRStatus.UNREADABLE,
            validation_notes="Could not read a valid employee ID and name matching failed"
        )

    def _is_valid_id_format(self, emp_id: str) -> bool:
        return bool(self.id_pattern.match(emp_id))

    def _find_exact_match(self, emp_id: str, sheet_name: Optional[str] = None) -> Optional[Employee]:
        try:
            emp = self.workbook_service.get_employee_as_object(emp_id)
            if emp and sheet_name:
                if emp.sheet_name.upper() != sheet_name.upper():
                    logging.info(
                        f"SHEET_SCOPED: _find_exact_match rejected cross-sheet "
                        f"emp_id='{emp_id}' emp_sheet='{emp.sheet_name}' "
                        f"active_sheet='{sheet_name}'"
                    )
                    return None
                logging.info(
                    f"SHEET_SCOPED: _find_exact_match matched "
                    f"emp_id='{emp_id}' sheet='{sheet_name}'"
                )
            return emp
        except Exception as e:
            logging.error(f"Database lookup failed for {emp_id}: {e}")
            return None

    def _find_name_match(self, ocr_name: str, sheet_name: Optional[str] = None) -> Optional[Employee]:
        """Find employee by name with fuzzy matching, respecting sheet scope."""
        try:
            if sheet_name:
                candidates = self.workbook_service.get_employees_by_sheet_as_objects(sheet_name)
            else:
                candidates = self.workbook_service.employees

            if not candidates:
                return None

            best_match = None
            best_score = 0

            name_upper = ocr_name.upper()
            
            for emp in candidates:
                emp_name = emp.name.upper() if emp.name else ""
                
                # Exact match
                if emp_name == name_upper:
                    score = 100
                # Name contains the OCR name
                elif name_upper in emp_name:
                    score = 90
                # Employee name contains OCR name
                elif emp_name in name_upper:
                    score = 85
                else:
                    # Fuzzy match
                    score = fuzz.ratio(emp_name, name_upper)

                # Only consider matches above 80% similarity for name fallback
                if score >= 80 and score > best_score:
                    best_match = emp
                    best_score = score

            if best_match:
                logging.info(
                    f"NAME_FALLBACK: matched '{ocr_name}' to "
                    f"emp_id='{best_match.employee_id}' name='{best_match.name}' "
                    f"sheet='{best_match.sheet_name}' score={best_score}"
                )
                return best_match
            else:
                logging.info(
                    f"NAME_FALLBACK: no match found for '{ocr_name}' "
                    f"in sheet='{sheet_name or 'ALL'}' candidates={len(candidates)}"
                )
                return None

        except Exception as e:
            logging.error(f"Name matching failed for '{ocr_name}': {e}")
            return None

    def find_possible_matches(self, ocr_id: str, ocr_name: str, sheet_name: str, limit: int = 5) -> List[Dict]:
        try:
            sheet_emps = self.workbook_service.get_employees_by_sheet_as_objects(sheet_name)

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
            logging.info(
                f"MATCH_SEARCH: find_possible_matches ocr_id='{ocr_id}' "
                f"ocr_name='{ocr_name}' sheet='{sheet_name}' "
                f"db_matches={len(sheet_emps)} returned={len(scored)} displayed={min(len(scored), limit)}"
            )
            return scored[:limit]

        except Exception as e:
            logging.error(f"find_possible_matches failed: {e}")
            return []

    def manual_correction(self, result: OCRValidationResult,
                          corrected_id: str = None,
                          selected_employee: Employee = None,
                          sheet_name: Optional[str] = None) -> OCRValidationResult:
        if corrected_id:
            corrected_item = {'id': corrected_id, 'name': result.ocr_name}
            corrected_result = self._validate_single_result(corrected_item, sheet_name=sheet_name)
            corrected_result.manually_corrected = True
            corrected_result.original_ocr_id = result.original_ocr_id
            corrected_result.original_ocr_name = result.original_ocr_name
            logging.info(
                f"SHEET_SCOPED: manual_correction corrected_id='{corrected_id}' "
                f"sheet='{sheet_name}' matched={corrected_result.matched_employee is not None}"
            )
            return corrected_result

        elif selected_employee:
            if sheet_name and selected_employee.sheet_name.upper() != sheet_name.upper():
                logging.error(
                    f"SHEET_SCOPED: REJECTED cross-sheet correction "
                    f"employee={selected_employee.employee_id} "
                    f"emp_sheet='{selected_employee.sheet_name}' "
                    f"active_sheet='{sheet_name}'"
                )
                raise ValueError(
                    f"Cannot match employee {selected_employee.employee_id} "
                    f"from sheet '{selected_employee.sheet_name}' "
                    f"to active sheet '{sheet_name}'."
                )
            result.matched_employee = selected_employee
            result.status = OCRStatus.CONFIRMED
            result.validation_notes = "Manually matched employee"
            result.manually_corrected = True
            result.is_checked = True
            result.checkbox_enabled = True
            return result

        return result

        return result

    def _score_employees(self, query: str, employees: List[Employee], diagnostics: Dict = None) -> List[Dict]:
        q = query.strip().upper()
        if not q:
            return [{"employee": e, "score": 0} for e in employees]

        scored = []
        for emp in employees:
            try:
                eid = emp.employee_id.upper() if emp.employee_id else ""
                name = emp.name.upper() if emp.name else ""

                if eid == q:
                    score = 100
                elif name == q:
                    score = 95
                elif eid.startswith(q):
                    score = 90
                elif name.startswith(q):
                    score = 85
                elif q in eid:
                    score = 80
                elif q in name:
                    score = 75
                else:
                    id_ratio = fuzz.ratio(eid, q)
                    name_ratio = fuzz.partial_ratio(name, q)
                    score = max(id_ratio, name_ratio)
                    if score < 10:
                        if diagnostics is not None:
                            diagnostics["filtered_by_score"] += 1
                            diagnostics["dropped"].append(
                                f"emp_id={emp.employee_id} name='{emp.name}' "
                                f"sheet='{emp.sheet_name}' score={score:.1f}"
                            )
                        continue

                scored.append({"employee": emp, "score": score})
            except Exception as e:
                logging.warning(
                    f"CORRECTION_SEARCH: score error for {emp.employee_id}: {e}"
                )
                continue

        return scored

    def search_employees_for_manual_match(self, query: str, sheet_name: Optional[str] = None, limit: int = 100) -> List[Employee]:
        q = query.strip()
        if not q:
            return []

        diagnostics = {
            "query": q,
            "sheet_name": sheet_name,
            "exact_match": None,
            "like_matches": 0,
            "scored": 0,
            "displayed": 0,
            "filtered_by_score": 0,
            "truncated_by_limit": 0,
            "dropped": [],
        }

        results = {}  # emp_id -> (employee, score)

        # Step 1: Exact ID match (with sheet filter)
        try:
            exact = self.workbook_service.get_employee_as_object(q.upper())
            if exact:
                # Apply sheet filter to exact match
                if sheet_name and exact.sheet_name.upper() != sheet_name.upper():
                    logging.info(
                        f"CORRECTION_SEARCH: exact match filtered by sheet - "
                        f"emp_id='{exact.employee_id}' emp_sheet='{exact.sheet_name}' "
                        f"active_sheet='{sheet_name}'"
                    )
                    exact = None
                
                if exact:
                    results[exact.employee_id] = (exact, 100)
                    diagnostics["exact_match"] = exact.employee_id
        except Exception as e:
            logging.warning(f"CORRECTION_SEARCH: exact lookup error: {e}")

        # Step 2: SQL LIKE search (broad, sheet-filtered)
        try:
            db_limit = limit * 3
            raw = self.workbook_service.search_employees_as_objects(
                q, db_limit, sheet_name=sheet_name
            )
            diagnostics["like_matches"] = len(raw)

            scored = self._score_employees(q, raw, diagnostics)
            for s in scored:
                eid = s["employee"].employee_id
                if eid not in results or s["score"] > results[eid][1]:
                    results[eid] = (s["employee"], s["score"])
        except Exception as e:
            logging.error(f"CORRECTION_SEARCH: LIKE search error: {e}")

        # Step 3: Sort by score descending
        sorted_results = sorted(results.values(), key=lambda x: x[1], reverse=True)
        diagnostics["scored"] = len(sorted_results)

        top = sorted_results[:limit]
        diagnostics["displayed"] = len(top)
        diagnostics["truncated_by_limit"] = max(0, len(sorted_results) - limit)

        # Log all dropped employees
        for emp_log in diagnostics["dropped"]:
            logging.info(f"CORRECTION_SEARCH: DROPPED {emp_log}")

        logging.info(
            f"CORRECTION_SEARCH: "
            f"query='{q}' sheet='{sheet_name or 'ALL'}' "
            f"exact={diagnostics['exact_match'] or 'none'} "
            f"like_matches={diagnostics['like_matches']} "
            f"scored={diagnostics['scored']} "
            f"displayed={diagnostics['displayed']} "
            f"truncated={diagnostics['truncated_by_limit']} "
            f"filtered_by_score={diagnostics['filtered_by_score']}"
        )
        return [emp for emp, _score in top]

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
