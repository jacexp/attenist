import logging
import os
import time
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QProgressDialog,
)

from workbook.loader import WorkbookLoader

from workbook.indexes.employee import EmployeeIndexer
from workbook.indexes.date import DateIndexer

from services.search_service import SearchService
from services.attendance_service import AttendanceService

# Configure Audit Logging
logging.basicConfig(
    filename="attenist.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

class MainWindow(QWidget):
    def __init__(self, workbook_path):
        super().__init__()

        self.setWindowTitle("Attenist")
        self.workbook_path = workbook_path

        try:
            # Load workbook
            self.workbook = WorkbookLoader().load(
                self.workbook_path
            )
        except PermissionError:
            QMessageBox.critical(
                self,
                "File Locked",
                f"Cannot open '{os.path.basename(self.workbook_path)}'.\n\nPlease close it in Excel and try again."
            )
            raise SystemExit

        self.employees = EmployeeIndexer().build(
            self.workbook
        )

        # Build dates from the first valid attendance sheet
        self.dates = {}
        for sheet in self.workbook.worksheets:
            has_employees = any(emp.sheet_name == sheet.title for emp in self.employees)
            if has_employees:
                self.dates = DateIndexer().build(sheet)
                if self.dates:
                    break

        if not self.dates:
            QMessageBox.critical(
                self,
                "Error",
                "No valid attendance dates found in workbook."
            )

        self.search_service = SearchService(
            self.employees
        )

        self.attendance_service = AttendanceService(
            self.workbook,
            self.employees,
            self.dates,
        )

        self.selected_employee = None

        # State Management
        self.unsaved_changes = 0
        self.last_save_time = time.time()

        self.build_ui()
        self.connect_signals()
        self.setup_shortcuts()

    def build_ui(self):
        main_layout = QHBoxLayout()
        
        # Left Panel: Data Entry
        entry_layout = QVBoxLayout()

        self.day_combo = QComboBox()
        available_days = sorted(self.dates.keys())
        for day in available_days:
            self.day_combo.addItem(str(day))
        
        if 14 in self.dates:
            self.day_combo.setCurrentText("14")

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Employee ID or Name")

        self.results_list = QListWidget()
        self.results_list.setFixedHeight(120)

        self.shift_combo = QComboBox()
        self.shift_combo.addItems(["A", "B", "C", "G", "WO", "AB"])

        self.mark_button = QPushButton("Mark Attendance")
        self.mark_button.setFixedHeight(40)

        entry_layout.addWidget(QLabel("Attendance Day"))
        entry_layout.addWidget(self.day_combo)
        entry_layout.addWidget(QLabel("Employee Search"))
        entry_layout.addWidget(self.search_box)
        entry_layout.addWidget(QLabel("Matches (Select One)"))
        entry_layout.addWidget(self.results_list)
        entry_layout.addWidget(QLabel("Shift"))
        entry_layout.addWidget(self.shift_combo)
        entry_layout.addWidget(self.mark_button)
        entry_layout.addStretch()

        # Right Panel: Change Summary
        summary_layout = QVBoxLayout()
        
        self.summary_list = QListWidget()
        self.summary_list.setMinimumWidth(300)
        
        self.status_label = QLabel("Unsaved Changes: 0")
        self.last_saved_label = QLabel(f"Last Saved: {time.strftime('%H:%M:%S', time.localtime(self.last_save_time))}")
        
        self.manual_save_button = QPushButton("Save Workbook (Ctrl+S)")
        self.manual_save_button.setStyleSheet("font-weight: bold; height: 50px;")
        self.manual_save_button.setEnabled(False)

        summary_layout.addWidget(QLabel("Pending Changes Summary"))
        summary_layout.addWidget(self.summary_list)
        summary_layout.addWidget(self.status_label)
        summary_layout.addWidget(self.last_saved_label)
        summary_layout.addWidget(self.manual_save_button)

        main_layout.addLayout(entry_layout)
        main_layout.addLayout(summary_layout)

        self.setLayout(main_layout)

    def connect_signals(self):
        self.search_box.textChanged.connect(self.on_search_changed)
        self.results_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.mark_button.clicked.connect(self.mark_attendance)
        self.manual_save_button.clicked.connect(self.perform_save)
        
        # Single-Enter Workflow: Mark from search box
        self.search_box.returnPressed.connect(self.mark_attendance)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.perform_save)

    def on_search_changed(self, text):
        text = text.strip()
        self.results_list.clear()
        self.selected_employee = None

        if not text:
            return

        results = self.search_service.search(text)

        if not results:
            return

        for result in results:
            emp = result["employee"]
            item = QListWidgetItem(
                f"{emp.employee_id} - {emp.name} ({emp.sheet_name})"
            )
            item.setData(32, emp)
            self.results_list.addItem(item)
        
        if self.results_list.count() == 1:
            self.results_list.setCurrentRow(0)

    def on_selection_changed(self):
        selected_items = self.results_list.selectedItems()
        if not selected_items:
            self.selected_employee = None
            return
        
        self.selected_employee = selected_items[0].data(32)

    def mark_attendance(self):
        if not self.selected_employee:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select an employee from the matches list.",
            )
            return

        day = int(self.day_combo.currentText())
        shift = self.shift_combo.currentText()
        emp_name = self.selected_employee.name

        # In-Memory Update (Instant)
        old_value = self.attendance_service.mark(
            self.selected_employee,
            day,
            shift,
        )

        # Audit Log
        logging.info(
            f"MARK (Memory): {self.selected_employee.employee_id} ({emp_name}) "
            f"Day {day} on {self.selected_employee.sheet_name}: "
            f"'{old_value}' -> '{shift}'"
        )

        # Update Summary Panel
        summary_text = f"Day {day}: {emp_name} -> {shift} ({self.selected_employee.sheet_name})"
        self.summary_list.addItem(summary_text)
        self.summary_list.scrollToBottom()

        # Update Dirty State
        self.unsaved_changes += 1
        self.status_label.setText(f"Unsaved Changes: {self.unsaved_changes}")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.manual_save_button.setEnabled(True)

        # Immediate UI Readiness
        self.search_box.clear()
        self.search_box.setFocus()

    def set_ui_enabled(self, enabled: bool):
        self.day_combo.setEnabled(enabled)
        self.search_box.setEnabled(enabled)
        self.results_list.setEnabled(enabled)
        self.shift_combo.setEnabled(enabled)
        self.mark_button.setEnabled(enabled)
        self.manual_save_button.setEnabled(enabled)

    def perform_save(self):
        if self.unsaved_changes == 0:
            return

        progress = QProgressDialog("Saving workbook...", None, 0, 0, self)
        progress.setWindowTitle("Please Wait")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        self.set_ui_enabled(False)
        self.status_label.setText("Saving workbook...")
        QApplication.processEvents()

        try:
            self.attendance_service.save(self.workbook_path)
            
            # Reset State
            self.unsaved_changes = 0
            self.last_save_time = time.time()
            self.status_label.setText("Unsaved Changes: 0")
            self.status_label.setStyleSheet("color: #666; font-weight: normal;")
            self.last_saved_label.setText(f"Last Saved: {time.strftime('%H:%M:%S', time.localtime(self.last_save_time))}")
            self.summary_list.clear()
            self.manual_save_button.setEnabled(False)
            
            logging.info(f"SAVE: Workbook saved to disk. Path: {self.workbook_path}")

        except PermissionError:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Cannot save to '{os.path.basename(self.workbook_path)}'.\nPlease close it in Excel."
            )
            self.status_label.setText(f"Save FAILED (Unsaved: {self.unsaved_changes})")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")
            self.status_label.setText("Save ERROR")
        finally:
            progress.close()
            self.set_ui_enabled(True)
            self.search_box.setFocus()

    def closeEvent(self, event: QCloseEvent):
        if self.unsaved_changes > 0:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have {self.unsaved_changes} unsaved changes.\nSave before exit?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                self.perform_save()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()