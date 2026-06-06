"""
Database Service - Business Logic Layer for Employee Management
"""
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from core.models import Employee
from database.employee_repository import EmployeeRepository


class DatabaseService:
    """Business logic layer for employee database operations."""
    
    def __init__(self, db_path: str = "employees.db"):
        self.repository = EmployeeRepository(db_path)
        self.migration_stats = {
            "total_scanned": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None
        }
    
    def sync_employees_from_workbook(self, employees: List[Employee]) -> Dict:
        """
        Sync employees from Excel workbook to SQLite database.
        Returns detailed statistics about the sync operation.
        """
        self.migration_stats = {
            "total_scanned": len(employees),
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "start_time": datetime.now().isoformat(),
            "end_time": None
        }
        
        # Log start of migration
        self.repository.log_migration_event("SYNC_START", None, None, 
                                           f"Scanning {len(employees)} employees from workbook")
        
        for employee in employees:
            try:
                # Check if employee exists
                existing = self.repository.get_employee_by_id(employee.employee_id)
                
                if existing:
                    # Update existing employee
                    old_values = json.dumps({
                        "name": existing["emp_name"],
                        "rank": existing["rank"],
                        "sheet": existing["sheet_name"],
                        "row": existing["row_number"]
                    })
                    
                    success = self.repository.update_employee(
                        employee.employee_id,
                        employee.name,
                        employee.rank,
                        employee.sheet_name,
                        employee.row
                    )
                    
                    if success:
                        self.migration_stats["updated"] += 1
                        new_values = json.dumps({
                            "name": employee.name,
                            "rank": employee.rank,
                            "sheet": employee.sheet_name,
                            "row": employee.row
                        })
                        self.repository.log_migration_event("UPDATE", employee.employee_id, 
                                                          old_values, new_values)
                    else:
                        self.migration_stats["errors"] += 1
                        self.repository.log_migration_event("UPDATE_ERROR", employee.employee_id,
                                                          None, f"Failed to update {employee.employee_id}")
                else:
                    # Insert new employee
                    success = self.repository.insert_employee(employee, synced_from_excel=True)
                    
                    if success:
                        self.migration_stats["inserted"] += 1
                        new_values = json.dumps({
                            "name": employee.name,
                            "rank": employee.rank,
                            "sheet": employee.sheet_name,
                            "row": employee.row
                        })
                        self.repository.log_migration_event("INSERT", employee.employee_id,
                                                          None, new_values)
                    else:
                        self.migration_stats["errors"] += 1
                        self.repository.log_migration_event("INSERT_ERROR", employee.employee_id,
                                                          None, f"Failed to insert {employee.employee_id}")
            
            except Exception as e:
                self.migration_stats["errors"] += 1
                self.repository.log_migration_event("SYNC_ERROR", 
                                                  getattr(employee, 'employee_id', 'UNKNOWN'),
                                                  None, f"Exception: {str(e)}")
        
        self.migration_stats["end_time"] = datetime.now().isoformat()
        
        # Log end of migration
        self.repository.log_migration_event("SYNC_END", None, None, 
                                           json.dumps(self.migration_stats))
        
        return self.migration_stats.copy()
    
    def search_employees(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search employees in SQLite database.
        Returns list of employee dictionaries compatible with UI.
        """
        return self.repository.search_employees(query, limit)
    
    def search_employees_as_objects(self, query: str, limit: int = 50) -> List[Employee]:
        """
        Search employees and return as Employee objects for backward compatibility.
        Used by existing search service and UI components.
        """
        db_results = self.repository.search_employees(query, limit)
        employee_objects = []
        
        for result in db_results:
            employee = Employee(
                employee_id=result["emp_id"],
                name=result["emp_name"],
                rank=result["rank"] or "",
                sheet_name=result["sheet_name"] or "",
                row=result["row_number"] or 0
            )
            employee_objects.append(employee)
        
        return employee_objects
    
    def get_employee_by_id(self, emp_id: str) -> Optional[Dict]:
        """Get employee by ID from database."""
        return self.repository.get_employee_by_id(emp_id)
    
    def get_employee_as_object(self, emp_id: str) -> Optional[Employee]:
        """Get employee as Employee object for backward compatibility."""
        result = self.repository.get_employee_by_id(emp_id)
        if result:
            return Employee(
                employee_id=result["emp_id"],
                name=result["emp_name"],
                rank=result["rank"] or "",
                sheet_name=result["sheet_name"] or "",
                row=result["row_number"] or 0
            )
        return None
    
    def add_employee(self, emp_id: str, emp_name: str, rank: str = "") -> bool:
        """Add new employee manually (not from Excel sync)."""
        # Create Employee object for manual entry
        employee = Employee(
            employee_id=emp_id,
            name=emp_name,
            rank=rank,
            sheet_name="",  # Manual entries don't have sheet info
            row=0
        )
        
        success = self.repository.insert_employee(employee, synced_from_excel=False)
        
        if success:
            self.repository.log_migration_event("MANUAL_ADD", emp_id, None,
                                               f"Manual entry: {emp_name}, {rank}")
        
        return success
    
    def update_employee(self, emp_id: str, emp_name: str, rank: str = "") -> bool:
        """Update existing employee."""
        # Get old values for logging
        existing = self.repository.get_employee_by_id(emp_id)
        if existing:
            old_values = json.dumps({
                "name": existing["emp_name"],
                "rank": existing["rank"]
            })
            
            success = self.repository.update_employee(emp_id, emp_name, rank)
            
            if success:
                new_values = json.dumps({
                    "name": emp_name,
                    "rank": rank
                })
                self.repository.log_migration_event("MANUAL_UPDATE", emp_id,
                                                   old_values, new_values)
            
            return success
        
        return False
    
    def delete_employee(self, emp_id: str) -> bool:
        """Delete employee."""
        # Get employee info for logging
        existing = self.repository.get_employee_by_id(emp_id)
        if existing:
            old_values = json.dumps({
                "name": existing["emp_name"],
                "rank": existing["rank"],
                "synced": existing["synced_from_excel"]
            })
            
            success = self.repository.delete_employee(emp_id)
            
            if success:
                self.repository.log_migration_event("DELETE", emp_id, old_values, None)
            
            return success
        
        return False
    
    def get_all_employees(self, limit: int = 1000) -> List[Dict]:
        """Get all employees from database."""
        return self.repository.get_all_employees(limit)
    
    def get_database_statistics(self) -> Dict:
        """Get comprehensive database statistics."""
        return self.repository.get_statistics()
    
    def generate_migration_report(self) -> Dict:
        """Generate comprehensive migration report."""
        stats = self.repository.get_statistics()
        history = self.repository.get_migration_history(50)
        
        # Analyze migration history
        sync_operations = [h for h in history if h["operation"].startswith("SYNC_")]
        manual_operations = [h for h in history if h["operation"].startswith("MANUAL_")]
        
        # Get latest sync stats
        latest_sync = None
        for event in history:
            if event["operation"] == "SYNC_END" and event["new_values"]:
                try:
                    latest_sync = json.loads(event["new_values"])
                    break
                except json.JSONDecodeError:
                    continue
        
        report = {
            "database_statistics": stats,
            "latest_sync_stats": latest_sync or self.migration_stats,
            "recent_operations": {
                "sync_operations": len(sync_operations),
                "manual_operations": len(manual_operations),
                "total_operations": len(history)
            },
            "migration_history": history[:10],  # Last 10 operations
            "data_integrity": self._check_data_integrity(),
            "report_generated_at": datetime.now().isoformat()
        }
        
        return report
    
    def _check_data_integrity(self) -> Dict:
        """Check data integrity and return status."""
        all_employees = self.repository.get_all_employees()
        
        integrity_report = {
            "total_records": len(all_employees),
            "missing_names": 0,
            "missing_ids": 0,
            "duplicate_ids": 0,
            "records_with_sheet_info": 0,
            "manual_entries": 0,
            "synced_entries": 0
        }
        
        seen_ids = set()
        
        for emp in all_employees:
            if not emp["emp_name"] or emp["emp_name"].strip() == "":
                integrity_report["missing_names"] += 1
            
            if not emp["emp_id"] or emp["emp_id"].strip() == "":
                integrity_report["missing_ids"] += 1
            
            if emp["emp_id"] in seen_ids:
                integrity_report["duplicate_ids"] += 1
            seen_ids.add(emp["emp_id"])
            
            if emp["sheet_name"] and emp["row_number"]:
                integrity_report["records_with_sheet_info"] += 1
            
            if emp["synced_from_excel"]:
                integrity_report["synced_entries"] += 1
            else:
                integrity_report["manual_entries"] += 1
        
        # Calculate integrity score
        total_issues = (integrity_report["missing_names"] + 
                       integrity_report["missing_ids"] + 
                       integrity_report["duplicate_ids"])
        
        if integrity_report["total_records"] > 0:
            integrity_score = max(0, 100 - (total_issues / integrity_report["total_records"]) * 100)
        else:
            integrity_score = 100
        
        integrity_report["integrity_score"] = round(integrity_score, 2)
        
        return integrity_report
    
    def cleanup_old_migration_logs(self, days_to_keep: int = 30) -> int:
        """Clean up old migration logs older than specified days."""
        # This is a simple implementation - in production you might want more sophisticated cleanup
        history = self.repository.get_migration_history(1000)
        cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        
        # For now, just return count - actual cleanup would require additional repository method
        old_logs = 0
        for log in history:
            try:
                log_time = datetime.fromisoformat(log["timestamp"]).timestamp()
                if log_time < cutoff_date:
                    old_logs += 1
            except:
                continue
        
        return old_logs
    
    def export_employees_to_dict(self) -> List[Dict]:
        """Export all employees as dictionary for backup/export purposes."""
        return self.repository.get_all_employees()
    
    def get_employees_by_sheet(self, sheet_name: str) -> List[Dict]:
        """Get all employees from a specific Excel sheet."""
        return self.repository.get_employees_by_sheet(sheet_name)