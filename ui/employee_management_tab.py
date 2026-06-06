from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QMessageBox,
    QHeaderView, QAbstractItemView, QSplitter
)
from PySide6.QtCore import Qt
from database.database_service import DatabaseService

class EmployeeManagementTab(QWidget):
    def __init__(self, database_service: DatabaseService):
        super().__init__()
        self.database_service = database_service
        self.build_ui()
        self.connect_signals()
        self.refresh_table()
    
    def build_ui(self):
        layout = QVBoxLayout()
        
        # Stats section
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Loading statistics...")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        
        self.refresh_button = QPushButton("Refresh")
        stats_layout.addWidget(self.refresh_button)
        
        layout.addLayout(stats_layout)
        
        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Add/Edit employee
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        left_layout.addWidget(QLabel("Employee Management"))
        
        # Employee ID
        left_layout.addWidget(QLabel("Employee ID:"))
        self.emp_id_input = QLineEdit()
        self.emp_id_input.setPlaceholderText("Enter employee ID")
        left_layout.addWidget(self.emp_id_input)
        
        # Employee Name
        left_layout.addWidget(QLabel("Employee Name:"))
        self.emp_name_input = QLineEdit()
        self.emp_name_input.setPlaceholderText("Enter employee name")
        left_layout.addWidget(self.emp_name_input)
        
        # Rank
        left_layout.addWidget(QLabel("Rank:"))
        self.rank_input = QLineEdit()
        self.rank_input.setPlaceholderText("Enter rank (optional)")
        left_layout.addWidget(self.rank_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Employee")
        self.update_button = QPushButton("Update Employee")
        self.clear_button = QPushButton("Clear")
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.clear_button)
        
        left_layout.addLayout(button_layout)
        left_layout.addStretch()
        
        left_panel.setLayout(left_layout)
        left_panel.setMaximumWidth(300)
        
        # Right panel - Employee list and search
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by ID or name")
        search_layout.addWidget(self.search_input)
        
        self.search_button = QPushButton("Search")
        search_layout.addWidget(self.search_button)
        
        self.show_all_button = QPushButton("Show All")
        search_layout.addWidget(self.show_all_button)
        
        right_layout.addLayout(search_layout)
        
        # Employee table
        self.employee_table = QTableWidget()
        self.employee_table.setColumnCount(5)
        self.employee_table.setHorizontalHeaderLabels([
            "Employee ID", "Name", "Rank", "Created", "Updated"
        ])
        
        # Configure table
        header = self.employee_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.Stretch)           # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Rank
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Created
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Updated
        
        self.employee_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.employee_table.setAlternatingRowColors(True)
        
        right_layout.addWidget(self.employee_table)
        
        # Delete button
        delete_layout = QHBoxLayout()
        delete_layout.addStretch()
        self.delete_button = QPushButton("Delete Selected Employee")
        self.delete_button.setStyleSheet("background-color: #ff6b6b; color: white;")
        delete_layout.addWidget(self.delete_button)
        
        right_layout.addLayout(delete_layout)
        
        right_panel.setLayout(right_layout)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])  # Give more space to table
        
        layout.addWidget(splitter)
        self.setLayout(layout)
    
    def connect_signals(self):
        self.add_button.clicked.connect(self.add_employee)
        self.update_button.clicked.connect(self.update_employee)
        self.clear_button.clicked.connect(self.clear_form)
        self.delete_button.clicked.connect(self.delete_employee)
        self.search_button.clicked.connect(self.search_employees)
        self.show_all_button.clicked.connect(self.refresh_table)
        self.refresh_button.clicked.connect(self.refresh_table)
        
        # Auto-search on text change
        self.search_input.textChanged.connect(self.auto_search)
        
        # Table selection
        self.employee_table.itemSelectionChanged.connect(self.on_table_selection)
    
    def refresh_table(self):
        """Refresh employee table with all employees."""
        try:
            employees = self.database_service.get_all_employees()
            self.populate_table(employees)
            self.update_stats()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load employees: {e}")
    
    def populate_table(self, employees):
        """Populate table with employee data."""
        self.employee_table.setRowCount(len(employees))
        
        for row, emp in enumerate(employees):
            self.employee_table.setItem(row, 0, QTableWidgetItem(emp["emp_id"]))
            self.employee_table.setItem(row, 1, QTableWidgetItem(emp["emp_name"]))
            self.employee_table.setItem(row, 2, QTableWidgetItem(emp["rank"] or ""))
            
            # Format dates
            created_date = emp["created_at"][:10] if emp["created_at"] else ""
            updated_date = emp["updated_at"][:10] if emp["updated_at"] else ""
            
            self.employee_table.setItem(row, 3, QTableWidgetItem(created_date))
            self.employee_table.setItem(row, 4, QTableWidgetItem(updated_date))
    
    def update_stats(self):
        """Update statistics display."""
        try:
            stats = self.database_service.get_database_statistics()
            self.stats_label.setText(
                f"Total Employees: {stats['total_employees']} | "
                f"Added Today: {stats['added_today']} | "
                f"Updated Today: {stats['updated_today']}"
            )
        except Exception as e:
            self.stats_label.setText(f"Stats unavailable: {e}")
    
    def add_employee(self):
        """Add new employee to database."""
        emp_id = self.emp_id_input.text().strip()
        emp_name = self.emp_name_input.text().strip()
        rank = self.rank_input.text().strip()
        
        if not emp_id or not emp_name:
            QMessageBox.warning(self, "Validation Error", "Employee ID and Name are required.")
            return
        
        try:
            success = self.database_service.add_employee(emp_id, emp_name, rank)
            if success:
                QMessageBox.information(self, "Success", f"Employee {emp_id} added successfully.")
                self.clear_form()
                self.refresh_table()
            else:
                QMessageBox.warning(self, "Duplicate Employee", f"Employee ID {emp_id} already exists.")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to add employee: {e}")
    
    def update_employee(self):
        """Update existing employee in database."""
        emp_id = self.emp_id_input.text().strip()
        emp_name = self.emp_name_input.text().strip()
        rank = self.rank_input.text().strip()
        
        if not emp_id or not emp_name:
            QMessageBox.warning(self, "Validation Error", "Employee ID and Name are required.")
            return
        
        try:
            success = self.database_service.update_employee(emp_id, emp_name, rank)
            if success:
                QMessageBox.information(self, "Success", f"Employee {emp_id} updated successfully.")
                self.clear_form()
                self.refresh_table()
            else:
                QMessageBox.warning(self, "Employee Not Found", f"Employee ID {emp_id} not found.")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to update employee: {e}")
    
    def delete_employee(self):
        """Delete selected employee from database."""
        current_row = self.employee_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an employee to delete.")
            return
        
        emp_id = self.employee_table.item(current_row, 0).text()
        emp_name = self.employee_table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete employee {emp_id} ({emp_name})?\n\n"
            f"This will only remove them from the database, not from Excel files.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success = self.database_service.delete_employee(emp_id)
                if success:
                    QMessageBox.information(self, "Success", f"Employee {emp_id} deleted successfully.")
                    self.refresh_table()
                else:
                    QMessageBox.warning(self, "Delete Failed", f"Employee {emp_id} not found.")
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to delete employee: {e}")
    
    def search_employees(self):
        """Search employees by query."""
        query = self.search_input.text().strip()
        if not query:
            self.refresh_table()
            return
        
        try:
            employees = self.database_service.search_employees(query)
            self.populate_table(employees)
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Search failed: {e}")
    
    def auto_search(self, text):
        """Auto-search as user types."""
        if len(text) >= 2:
            self.search_employees()
        elif len(text) == 0:
            self.refresh_table()
    
    def on_table_selection(self):
        """Handle table row selection - populate form for editing."""
        current_row = self.employee_table.currentRow()
        if current_row >= 0:
            emp_id = self.employee_table.item(current_row, 0).text()
            emp_name = self.employee_table.item(current_row, 1).text()
            rank = self.employee_table.item(current_row, 2).text()
            
            # Populate form for editing
            self.emp_id_input.setText(emp_id)
            self.emp_name_input.setText(emp_name)
            self.rank_input.setText(rank)
    
    def clear_form(self):
        """Clear input form."""
        self.emp_id_input.clear()
        self.emp_name_input.clear()
        self.rank_input.clear()
        self.employee_table.clearSelection()