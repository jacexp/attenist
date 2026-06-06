"""
Employee Repository - Data Access Layer for SQLite Employee Database
"""
import sqlite3
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from core.models import Employee


class EmployeeRepository:
    """Pure data access layer for employee database operations."""
    
    def __init__(self, db_path: str = "employees.db"):
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Create database and tables if they don't exist, and apply migrations."""
        if not os.path.exists(self.db_path):
            self._create_database()
            self._migrate_schema()
        else:
            # Ensure base tables exist and then migrate
            self._create_tables()
            self._migrate_schema()
    
    def _migrate_schema(self):
        """Check for missing columns and upgrade the database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # 1. Get current columns
            cursor.execute("PRAGMA table_info(employees)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # 2. Define required columns and their types (for migrations)
            required_columns = {
                "sheet_name": "TEXT",
                "row_number": "INTEGER",
                "synced_from_excel": "INTEGER DEFAULT 1"
            }
            
            migrations_applied = 0
            for col_name, col_type in required_columns.items():
                if col_name not in existing_columns:
                    logging.info(f"Migrating database: Adding missing column {col_name} ({col_type})")
                    cursor.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}")
                    migrations_applied += 1
            
            if migrations_applied > 0:
                # Re-create indexes that depend on new columns
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_sheet ON employees(sheet_name)")
                conn.commit()
                logging.info(f"Database schema upgraded successfully. Applied {migrations_applied} migrations.")
                
                # Update version metadata
                self._update_schema_version(conn)
                
        except Exception as e:
            logging.error(f"Schema migration failed: {e}")
            # We don't raise here to allow app to try and start, 
            # though some operations might fail.
        finally:
            conn.close()

    def _update_schema_version(self, conn):
        """Track the current schema version in metadata table."""
        try:
            cursor = conn.cursor()
            # Ensure metadata table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Update version to '2.0' (since we added sheet/row info)
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value) 
                VALUES ('schema_version', '2.0')
            """)
            conn.commit()
        except Exception as e:
            logging.error(f"Failed to update schema version: {e}")

    
    def _create_database(self):
        """Create new database with schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            self._create_tables(conn)
        finally:
            conn.close()
    
    def _create_tables(self, conn=None):
        """Create base tables in database."""
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            should_close = True
        else:
            should_close = False
        
        try:
            cursor = conn.cursor()
            
            # Base employees table (minimum required columns)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    emp_id TEXT PRIMARY KEY,
                    emp_name TEXT NOT NULL,
                    rank TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Only create indexes for columns that are guaranteed to exist in base schema
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_emp_name ON employees(emp_name)
            """)
            
            # Migration metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Migration log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migration_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    emp_id TEXT,
                    old_values TEXT,
                    new_values TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            
            conn.commit()
        finally:
            if should_close:
                conn.close()
    
    def insert_employee(self, employee: Employee, synced_from_excel: bool = True) -> bool:
        """Insert new employee. Returns True if successful."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO employees (
                    emp_id, emp_name, rank, sheet_name, row_number, 
                    created_at, updated_at, synced_from_excel
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                employee.employee_id, employee.name, employee.rank,
                employee.sheet_name, employee.row, now, now,
                1 if synced_from_excel else 0
            ))
            
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def update_employee(self, emp_id: str, emp_name: str, rank: str = "", 
                       sheet_name: str = None, row_number: int = None) -> bool:
        """Update existing employee. Returns True if found and updated."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            if sheet_name is not None and row_number is not None:
                cursor.execute("""
                    UPDATE employees 
                    SET emp_name = ?, rank = ?, sheet_name = ?, row_number = ?, updated_at = ?
                    WHERE emp_id = ?
                """, (emp_name, rank, sheet_name, row_number, now, emp_id))
            else:
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
    
    def get_employee_by_id(self, emp_id: str) -> Optional[Dict]:
        """Get employee by ID."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emp_id, emp_name, rank, sheet_name, row_number, 
                       created_at, updated_at, synced_from_excel
                FROM employees WHERE emp_id = ?
            """, (emp_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "emp_id": row[0],
                    "emp_name": row[1],
                    "rank": row[2],
                    "sheet_name": row[3],
                    "row_number": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                    "synced_from_excel": bool(row[7])
                }
            return None
        finally:
            conn.close()
    
    def search_employees(self, query: str, limit: int = 50, sheet_name: Optional[str] = None) -> List[Dict]:
        """Search employees by name or ID, optionally filtered by sheet."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            if sheet_name:
                cursor.execute("""
                    SELECT emp_id, emp_name, rank, sheet_name, row_number,
                           created_at, updated_at, synced_from_excel
                    FROM employees 
                     WHERE (emp_id LIKE ? OR emp_name LIKE ?)
                     AND UPPER(sheet_name) = UPPER(?)
                     ORDER BY emp_name
                     LIMIT ?
                 """, (f"%{query}%", f"%{query}%", sheet_name, limit))
            else:
                cursor.execute("""
                    SELECT emp_id, emp_name, rank, sheet_name, row_number,
                           created_at, updated_at, synced_from_excel
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
                    "sheet_name": row[3],
                    "row_number": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                    "synced_from_excel": bool(row[7])
                })
            
            return results
        finally:
            conn.close()
    
    def get_all_employees(self, limit: int = 1000) -> List[Dict]:
        """Get all employees with optional limit."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emp_id, emp_name, rank, sheet_name, row_number,
                       created_at, updated_at, synced_from_excel
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
                    "sheet_name": row[3],
                    "row_number": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                    "synced_from_excel": bool(row[7])
                })
            
            return results
        finally:
            conn.close()
    
    def get_employees_by_sheet(self, sheet_name: str) -> List[Dict]:
        """Get all employees from a specific sheet."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                 SELECT emp_id, emp_name, rank, sheet_name, row_number,
                        created_at, updated_at, synced_from_excel
                 FROM employees 
                 WHERE UPPER(sheet_name) = UPPER(?)
                 ORDER BY row_number
             """, (sheet_name,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "emp_id": row[0],
                    "emp_name": row[1],
                    "rank": row[2],
                    "sheet_name": row[3],
                    "row_number": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                    "synced_from_excel": bool(row[7])
                })
            
            return results
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM employees")
            total_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM employees WHERE synced_from_excel = 1")
            synced_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM employees WHERE synced_from_excel = 0")
            manual_count = cursor.fetchone()[0]
            
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
            
            cursor.execute("SELECT COUNT(DISTINCT sheet_name) FROM employees WHERE sheet_name IS NOT NULL")
            sheet_count = cursor.fetchone()[0]
            
            return {
                "total_employees": total_count,
                "synced_from_excel": synced_count,
                "manual_entries": manual_count,
                "added_today": added_today,
                "updated_today": updated_today,
                "unique_sheets": sheet_count
            }
        finally:
            conn.close()
    
    def log_migration_event(self, operation: str, emp_id: str = None, 
                           old_values: str = None, new_values: str = None):
        """Log migration events for reporting."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO migration_log (operation, emp_id, old_values, new_values, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (operation, emp_id, old_values, new_values, now))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_migration_history(self, limit: int = 100) -> List[Dict]:
        """Get migration history for reporting."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT operation, emp_id, old_values, new_values, timestamp
                FROM migration_log
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "operation": row[0],
                    "emp_id": row[1],
                    "old_values": row[2],
                    "new_values": row[3],
                    "timestamp": row[4]
                })
            
            return results
        finally:
            conn.close()
    
    def clear_synced_employees(self) -> int:
        """Clear all employees marked as synced from Excel. Returns count of deleted records."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM employees WHERE synced_from_excel = 1")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()