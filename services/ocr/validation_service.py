"""
OCR Validation Service
Handles ID validation, SQLite matching, and status assignment for OCR results.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from enum import Enum
from database.database_service import DatabaseService
from core.models import Employee


class OCRStatus(Enum):
    """Status enumeration for OCR validation results."""
    CONFIRMED = "CONFIRMED"      # Valid ID with exact SQLite match
    REVIEW = "REVIEW"           # Valid ID but needs manual review
    UNMATCHED = "UNMATCHED"     # Valid ID format but no SQLite match
    INVALID = "INVALID"         # Invalid ID format


class OCRValidationResult:
    """Container for OCR validation results."""
    
    def __init__(self, ocr_id: str, ocr_name: str, status: OCRStatus, 
                 matched_employee: Optional[Employee] = None, 
                 validation_notes: str = ""):
        self.ocr_id = ocr_id
        self.ocr_name = ocr_name
        self.status = status
        self.matched_employee = matched_employee
        self.validation_notes = validation_notes
        
        # UI control states
        self.is_checked = status == OCRStatus.CONFIRMED
        self.checkbox_enabled = status == OCRStatus.CONFIRMED
        self.shift = ""  # Will be set by user
        
        # Manual correction tracking
        self.manually_corrected = False
        self.original_ocr_id = ocr_id
        self.original_ocr_name = ocr_name
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
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
    """Service for validating OCR results and matching against SQLite database."""
    
    def __init__(self, database_service: DatabaseService):
        """
        Initialize validation service.
        
        Args:
            database_service: DatabaseService instance for employee lookups
        """
        self.database_service = database_service
        
        # ID validation regex: ^[A-Z]{1,4}\d{2,5}$
        self.id_pattern = re.compile(r'^[A-Z]{1,4}\d{2,5}$')
        
        # Statistics tracking
        self.validation_stats = {
            'total_processed': 0,
            'confirmed': 0,
            'unmatched': 0,
            'invalid': 0,
            'review': 0
        }
    
    def validate_ocr_results(self, ocr_data: List[Dict]) -> List[OCRValidationResult]:
        """
        Validate OCR results and match against SQLite database.
        
        Args:
            ocr_data: List of OCR results with 'id' and 'name' keys
            
        Returns:
            List of OCRValidationResult objects
        """
        validation_results = []
        self.validation_stats = {
            'total_processed': 0,
            'confirmed': 0,
            'unmatched': 0,
            'invalid': 0,
            'review': 0
        }
        
        logging.info(f"Starting validation of {len(ocr_data)} OCR results")
        
        for ocr_item in ocr_data:
            try:
                result = self._validate_single_result(ocr_item)
                validation_results.append(result)
                
                # Update statistics
                self.validation_stats['total_processed'] += 1
                self.validation_stats[result.status.value.lower()] += 1
                
            except Exception as e:
                logging.error(f"Failed to validate OCR item {ocr_item}: {e}")
                # Create error result
                error_result = OCRValidationResult(
                    ocr_id=ocr_item.get('id', 'ERROR'),
                    ocr_name=ocr_item.get('name', 'ERROR'),
                    status=OCRStatus.INVALID,
                    validation_notes=f"Validation error: {e}"
                )
                validation_results.append(error_result)
                self.validation_stats['total_processed'] += 1
                self.validation_stats['invalid'] += 1
        
        logging.info(f"Validation complete: {self.validation_stats}")
        return validation_results
    
    def _validate_single_result(self, ocr_item: Dict) -> OCRValidationResult:
        """
        Validate a single OCR result.
        
        Args:
            ocr_item: Dict with 'id' and 'name' keys
            
        Returns:
            OCRValidationResult object
        """
        ocr_id = ocr_item.get('id', '').strip().upper()
        ocr_name = ocr_item.get('name', '').strip().upper()
        
        # Step 1: Validate ID format
        if not self._is_valid_id_format(ocr_id):
            return OCRValidationResult(
                ocr_id=ocr_id,
                ocr_name=ocr_name,
                status=OCRStatus.INVALID,
                validation_notes=f"Invalid ID format. Expected pattern: [A-Z]{{1,4}}[0-9]{{2,5}}"
            )
        
        # Step 2: Try exact SQLite match
        matched_employee = self._find_exact_match(ocr_id)
        
        if matched_employee:
            # Exact match found
            name_similarity = self._calculate_name_similarity(ocr_name, matched_employee.name.upper())
            
            if name_similarity > 0.8:  # High confidence match
                return OCRValidationResult(
                    ocr_id=ocr_id,
                    ocr_name=ocr_name,
                    status=OCRStatus.CONFIRMED,
                    matched_employee=matched_employee,
                    validation_notes=f"Exact ID match with {name_similarity:.1%} name similarity"
                )
            else:
                # ID matches but name is very different - needs review
                return OCRValidationResult(
                    ocr_id=ocr_id,
                    ocr_name=ocr_name,
                    status=OCRStatus.REVIEW,
                    matched_employee=matched_employee,
                    validation_notes=f"ID match but low name similarity ({name_similarity:.1%}). Please verify."
                )
        else:
            # No exact match found
            return OCRValidationResult(
                ocr_id=ocr_id,
                ocr_name=ocr_name,
                status=OCRStatus.UNMATCHED,
                validation_notes="Valid ID format but no matching employee found in database"
            )
    
    def _is_valid_id_format(self, emp_id: str) -> bool:
        """
        Validate employee ID format using regex.
        
        Args:
            emp_id: Employee ID to validate
            
        Returns:
            True if format is valid, False otherwise
        """
        return bool(self.id_pattern.match(emp_id))
    
    def _find_exact_match(self, emp_id: str) -> Optional[Employee]:
        """
        Find exact employee match in SQLite database.
        
        Args:
            emp_id: Employee ID to search for
            
        Returns:
            Employee object if found, None otherwise
        """
        try:
            return self.database_service.get_employee_as_object(emp_id)
        except Exception as e:
            logging.error(f"Database lookup failed for {emp_id}: {e}")
            return None
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names using simple algorithm.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not name1 or not name2:
            return 0.0
        
        # Simple similarity calculation
        # In production, you might want to use more sophisticated algorithms
        
        # Exact match
        if name1 == name2:
            return 1.0
        
        # Check if one name contains the other
        if name1 in name2 or name2 in name1:
            return 0.9
        
        # Calculate character overlap
        set1 = set(name1)
        set2 = set(name2)
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        
        if len(union) == 0:
            return 0.0
        
        return len(intersection) / len(union)
    
    def manual_correction(self, result: OCRValidationResult, 
                         corrected_id: str = None, 
                         selected_employee: Employee = None) -> OCRValidationResult:
        """
        Apply manual correction to a validation result.
        
        Args:
            result: Original validation result
            corrected_id: Manually corrected ID (optional)
            selected_employee: Manually selected employee (optional)
            
        Returns:
            Updated validation result
        """
        if corrected_id:
            # Re-validate with corrected ID
            corrected_item = {'id': corrected_id, 'name': result.ocr_name}
            corrected_result = self._validate_single_result(corrected_item)
            corrected_result.manually_corrected = True
            corrected_result.original_ocr_id = result.original_ocr_id
            corrected_result.original_ocr_name = result.original_ocr_name
            return corrected_result
        
        elif selected_employee:
            # Use manually selected employee
            result.matched_employee = selected_employee
            result.status = OCRStatus.CONFIRMED
            result.validation_notes = "Manually matched employee"
            result.manually_corrected = True
            result.is_checked = True
            result.checkbox_enabled = True
            return result
        
        return result
    
    def search_employees_for_manual_match(self, query: str, limit: int = 10) -> List[Employee]:
        """
        Search employees for manual matching during correction.
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of matching Employee objects
        """
        try:
            return self.database_service.search_employees_as_objects(query, limit)
        except Exception as e:
            logging.error(f"Employee search failed for query '{query}': {e}")
            return []
    
    def get_validation_statistics(self) -> Dict:
        """
        Get validation statistics.
        
        Returns:
            Dictionary containing validation statistics
        """
        return self.validation_stats.copy()
    
    def filter_ready_for_commit(self, results: List[OCRValidationResult]) -> List[OCRValidationResult]:
        """
        Filter results that are ready for batch commit (per-row checks only).
        Global shift check is done at batch level in UI.
        
        Args:
            results: List of validation results
            
        Returns:
            List of results ready for commit (checked, confirmed, matched)
        """
        ready_results = []
        
        for result in results:
            if (result.is_checked and 
                result.status == OCRStatus.CONFIRMED and 
                result.matched_employee):
                ready_results.append(result)
        
        return ready_results
    
    def validate_commit_readiness(self, results: List[OCRValidationResult]) -> Tuple[List[OCRValidationResult], List[str]]:
        """
        Validate which results are ready for commit and return warnings.
        Global shift check is done at batch level in UI.
        
        Args:
            results: List of validation results
            
        Returns:
            Tuple of (ready_results, warnings)
        """
        ready_results = []
        warnings = []
        
        for result in results:
            if not result.is_checked:
                continue  # Skip unchecked items
            
            if result.status != OCRStatus.CONFIRMED:
                warnings.append(f"Row {result.ocr_id}: Status is {result.status.value}, not CONFIRMED")
                continue
            
            if not result.matched_employee:
                warnings.append(f"Row {result.ocr_id}: No matched employee")
                continue
            
            # All checks passed (shift is now global, validated at batch level)
            ready_results.append(result)
        
        return ready_results, warnings