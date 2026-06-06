import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from core.models import Employee

class EmployeeDatabase:
    def __init__(self, db_path: str = "employees.db"):
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Create database and tables if they don't exist."""
        if not os.path.exists(self.db_path):
            self._create_database()
        else:
            # Ensure tables exist even if db file exists
            self._create_tables()
    
    def _create_database(self):
        """Create new database with schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            self._create_tables(conn)
        finally:
            conn.close()
    
    def _create_tables(self, conn=None):
        """Create tables in database."""
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            should_close = True
        else:
            should_close = False
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    emp_id TEXT PRIMARY KEY,
                    emp_name TEXT NOT NULL,
                    rank TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create index for faster name searches
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_emp_name ON employees(emp_name)
            """)
            
            conn.commit()
        finally:
            if should_close:
                conn.close()
    
    def sync_employee(self, employee: Employee) -> bool:
        """Insert or update employee record. Returns True if inserted, False if updated."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Check if employee exists
            cursor.execute("SELECT emp_id FROM employees WHERE emp_id = ?", (employee.employee_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update existing employee
                cursor.execute("""
                    UPDATE employees 
                    SET emp_name = ?, rank = ?, updated_at = ?
                    WHERE emp_id = ?
                """, (employee.name, employee.rank, now, employee.employee_id))
                return False
            else:
                # Insert new employee
                cursor.execute("""
                    INSERT INTO employees (emp_id, emp_name, rank, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (employee.employee_id, employee.name, employee.rank, now, now))
                return True
        finally:
            conn.commit()
            conn.close()
    
    def sync_employees(self, employees: List[Employee]) -> dict:
        """Sync multiple employees. Returns stats."""
        stats = {"inserted": 0, "updated": 0, "total": len(employees)}
        
        for employee in employees:
            is_new = self.sync_employee(employee)
            if is_new:
                stats["inserted"] += 1
            else:
                stats["updated"] += 1
        
        return stats
    
    def get_employee(self, emp_id: str) -> Optional[dict]:
        """Get employee by ID."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emp_id, emp_name, rank, created_at, updated_at
                FROM employees WHERE emp_id = ?
            """, (emp_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "emp_id": row[0],
                    "emp_name": row[1],
                    "rank": row[2],
                    "created_at": row[3],
                    "updated_at": row[4]
                }
            return None
        finally:
            conn.close()
    
    def search_employees(self, query: str, limit: int = 50) -> List[dict]:
        """Search employees by name or ID."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Search by ID or name (case insensitive)
            cursor.execute("""
                SELECT emp_id, emp_name, rank, created_at, updated_at
                FROM employees 
                WHERE emp_id LIKE ? OR emp_name LIKE ?
                ORDER BY emp_name
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "emp_id": row[0],
                    "emp_name": row[1],
                    "rank": row[2],
                    "created_at": row[3],
                    "updated_at": row[4]
                })
            
            return results
        finally:
            conn.close()
    
    def get_all_employees(self, limit: int = 1000) -> List[dict]:
        """Get all employees with optional limit."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emp_id, emp_name, rank, created_at, updated_at
                FROM employees 
                ORDER BY emp_name
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "emp_id": row[0],
                    "emp_name": row[1],
                    "rank": row[2],
                    "created_at": row[3],
                    "updated_at": row[4]
                })
            
            return results
        finally:
            conn.close()
    
    def add_employee(self, emp_id: str, emp_name: str, rank: str = "") -> bool:
        """Add new employee. Returns True if successful, False if already exists."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO employees (emp_id, emp_name, rank, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (emp_id, emp_name, rank, now, now))
            
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Employee already exists
            return False
        finally:
            conn.close()
    
    def update_employee(self, emp_id: str, emp_name: str, rank: str = "") -> bool:
        """Update existing employee. Returns True if found and updated."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute("""
                UPDATE employees 
                SET emp_name = ?, rank = ?, updated_at = ?
                WHERE emp_id = ?
            """, (emp_name, rank, now, emp_id))
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def delete_employee(self, emp_id: str) -> bool:
        """Delete employee. Returns True if found and deleted."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM employees WHERE emp_id = ?", (emp_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM employees")
            total_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM employees 
                WHERE date(created_at) = date('now')
            """)
            added_today = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM employees 
                WHERE date(updated_at) = date('now') AND date(created_at) != date('now')
            """)
            updated_today = cursor.fetchone()[0]
            
            return {
                "total_employees": total_count,
                "added_today": added_today,
                "updated_today": updated_today
            }
        finally:
            conn.close()