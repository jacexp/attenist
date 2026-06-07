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
    QTabWidget,
)

from services.search_service import SearchService
from services.workbook_service import WorkbookService
from services.attendance_service import AttendanceService
from ui.ocr_attendance_tab import OCRAttendanceTab


class MainWindow(QWidget):
    def __init__(self, workbook, employees, dates, workbook_path):
        super().__init__()

        self.setWindowTitle("Attenist")
        self.workbook_path = workbook_path
        self.workbook = workbook
        self.employees = employees
        self.dates = dates

        self.workbook_service = WorkbookService(employees)

        self.search_service = SearchService(
            workbook_service=self.workbook_service
        )

        self.attendance_service = AttendanceService(
            self.workbook,
            self.employees,
            self.dates,
        )

        self.selected_employee = None
        self.active_sheet_name = None

        # State Management
        self.unsaved_changes = 0
        self.last_save_time = time.time()

        self.build_ui()
        self.connect_signals()
        self.setup_shortcuts()

    def build_ui(self):
        main_layout = QVBoxLayout()
        
        # Sheet Selector Row
        sheet_row = QHBoxLayout()
        sheet_row.addWidget(QLabel("Active Sheet:"))
        self.sheet_selector = QComboBox()
        
        for sheet in self.workbook.worksheets:
            has_employees = any(emp.sheet_name == sheet.title for emp in self.employees)
            if has_employees:
                self.sheet_selector.addItem(sheet.title)
        
        if self.sheet_selector.count() > 0:
            self.sheet_selector.setCurrentIndex(0)
            self.active_sheet_name = self.sheet_selector.currentText()
        
        sheet_row.addWidget(self.sheet_selector)
        sheet_row.addStretch()
        main_layout.addLayout(sheet_row)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Attendance tab
        attendance_tab = QWidget()
        self.build_attendance_ui(attendance_tab)
        self.tab_widget.addTab(attendance_tab, "Attendance")
        
        # OCR Attendance tab (uses config.json for API key)
        self.ocr_attendance_tab = OCRAttendanceTab(
            self.workbook_service, 
            self.attendance_service,
            main_window=self
        )
        self.tab_widget.addTab(self.ocr_attendance_tab, "OCR Attendance")
        
        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)

    def build_attendance_ui(self, parent_widget):
        main_layout = QHBoxLayout()
        
        # Left Panel: Data Entry
        entry_layout = QVBoxLayout()

        self.day_combo = QComboBox()
        self.update_day_combo()

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

        parent_widget.setLayout(main_layout)

    def connect_signals(self):
        self.search_box.textChanged.connect(self.on_search_changed)
        self.results_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.mark_button.clicked.connect(self.mark_attendance)
        self.manual_save_button.clicked.connect(self.perform_save)
        self.sheet_selector.currentTextChanged.connect(self.on_sheet_changed)
        
        # Multiple ways to trigger "Mark Attendance" with Enter
        self.search_box.returnPressed.connect(self.mark_attendance)
        self.results_list.itemActivated.connect(self.mark_attendance) # Enter or Double-click on list
        self.day_combo.lineEdit().returnPressed.connect(self.mark_attendance) if self.day_combo.isEditable() else None
        self.shift_combo.lineEdit().returnPressed.connect(self.mark_attendance) if self.shift_combo.isEditable() else None

        # Enable arrow key navigation from search box to results list
        self.search_box.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.search_box and event.type() == Qt.KeyPress:
            if event.key() == Qt.Key_Down:
                if self.results_list.count() > 0:
                    curr = self.results_list.currentRow()
                    if curr < self.results_list.count() - 1:
                        self.results_list.setCurrentRow(curr + 1)
                    return True
            elif event.key() == Qt.Key_Up:
                if self.results_list.count() > 0:
                    curr = self.results_list.currentRow()
                    if curr > 0:
                        self.results_list.setCurrentRow(curr - 1)
                    return True
        return super().eventFilter(obj, event)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.perform_save)
        
        # Dedicated Enter/Return shortcut for marking attendance
        self.mark_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.mark_shortcut.activated.connect(self.mark_attendance)
        
        self.enter_shortcut = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self.enter_shortcut.activated.connect(self.mark_attendance)

    def on_search_changed(self, text):
        text = text.strip()
        self.results_list.clear()
        self.selected_employee = None

        if not text:
            return

        results = self.search_service.search(text, sheet_name=self.active_sheet_name)

        if not results:
            return

        for result in results:
            emp = result["employee"]
            item = QListWidgetItem(
                f"{emp.employee_id} - {emp.name} ({emp.sheet_name})"
            )
            item.setData(Qt.UserRole, emp)
            self.results_list.addItem(item)
        
        # Always highlight the top result for single-enter workflow
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    def on_selection_changed(self):
        selected_items = self.results_list.selectedItems()
        if not selected_items:
            self.selected_employee = None
            return
        
        self.selected_employee = selected_items[0].data(Qt.UserRole)

    def on_sheet_changed(self, sheet_name):
        # Prevent recursion and handle cancellation
        if hasattr(self, '_switching_sheet') and self._switching_sheet:
            return

        # Check if OCR tab allows change (shows confirmation dialog if data exists)
        if hasattr(self, 'ocr_attendance_tab'):
            if not self.ocr_attendance_tab.refresh_sheet():
                # Revert selection
                self._switching_sheet = True
                self.sheet_selector.setCurrentText(self.active_sheet_name)
                self._switching_sheet = False
                return

        self.active_sheet_name = sheet_name
        
        # Refresh days for the new sheet
        self.update_day_combo()

        # Refresh search if there is text
        if self.search_box.text():
            self.on_search_changed(self.search_box.text())

    def update_day_combo(self):
        """Update day_combo with available days for the current active sheet."""
        if not hasattr(self, 'day_combo'):
            return
            
        self.day_combo.clear()
        
        if not self.dates or not self.active_sheet_name:
            return

        # Handle both old global dict and new per-sheet dict structure
        sheet_dates = {}
        if self.active_sheet_name in self.dates:
            # New structure: dict[sheet_name, dict[day, col]]
            sheet_dates = self.dates[self.active_sheet_name]
        elif any(not isinstance(v, dict) for v in self.dates.values()):
            # Old/Simple structure: dict[day, col]
            sheet_dates = self.dates

        available_days = sorted(sheet_dates.keys())
        for day in available_days:
            self.day_combo.addItem(str(day))
            
        # Try to select current day as default
        from datetime import datetime
        current_day = str(datetime.now().day)
        index = self.day_combo.findText(current_day)
        if index >= 0:
            self.day_combo.setCurrentIndex(index)
        elif self.day_combo.count() > 0:
            self.day_combo.setCurrentIndex(0)

    def mark_attendance(self):
        # Only trigger if manual attendance tab is active
        if self.tab_widget.currentIndex() != 0:
            return

        # Prevent double-marking if search box is already cleared
        if not self.search_box.text().strip() and not self.selected_employee:
            return

        # Authoritative Fallback: Sync variable with UI state if possible
        if not self.selected_employee:
            current_item = self.results_list.currentItem()
            if current_item:
                self.selected_employee = current_item.data(Qt.UserRole)
                logging.info(f"MARK: Recovered selection from currentItem: {self.selected_employee.employee_id if self.selected_employee else 'None'}")
            elif self.results_list.count() > 0:
                # Pick the TOP result automatically if multiple exist but nothing explicitly selected
                self.selected_employee = self.results_list.item(0).data(Qt.UserRole)
                logging.info(f"MARK: Recovered selection from TOP item in list: {self.selected_employee.employee_id if self.selected_employee else 'None'}")

        if not self.selected_employee:
            logging.warning("MARK: Rejecting attendance mark - no selection found in variable or UI list.")
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
            self.active_sheet_name,
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