import os
import logging
from typing import List, Optional, Dict
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QTextEdit, QComboBox, QGroupBox,
    QFileDialog, QMessageBox, QFrame, QLineEdit,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QCheckBox, QTabWidget,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from services.ocr.ocr_service import OCRService, OCRServiceException
from services.ocr.validation_service import OCRValidationService, OCRValidationResult, OCRStatus
from services.workbook_service import WorkbookService
from core.models import Employee
from services.attendance_service import AttendanceService
from core.config import config
from ui.api_key_dialog import FirstLaunchManager


class OCRProcessingThread(QThread):
    progress_updated = Signal(int, str)
    ocr_completed = Signal(list, list)
    error_occurred = Signal(str)

    def __init__(self, image_paths: List[str], ocr_service: OCRService,
                 validation_service: OCRValidationService, sheet_name: Optional[str] = None):
        super().__init__()
        self.image_paths = image_paths
        self.ocr_service = ocr_service
        self.validation_service = validation_service
        self.sheet_name = sheet_name

    def run(self):
        try:
            total_images = len(self.image_paths)

            self.progress_updated.emit(10, "Starting OCR extraction...")

            all_extracted_data = []
            all_raw_responses = []

            for i, image_path in enumerate(self.image_paths):
                self.progress_updated.emit(
                    10 + (40 * (i + 1) // total_images),
                    f"Processing image {i + 1}/{total_images}: {Path(image_path).name}"
                )

                try:
                    extracted_data, raw_response = self.ocr_service.extract_attendance_from_image(image_path)
                    all_extracted_data.extend(extracted_data)
                    all_raw_responses.append(raw_response)
                except Exception as e:
                    logging.error(f"OCR failed for {image_path}: {e}")
                    all_raw_responses.append(f"Error processing {image_path}: {e}")

            self.progress_updated.emit(60, "Validating and matching employees...")

            validation_results = self.validation_service.validate_ocr_results(
                all_extracted_data, sheet_name=self.sheet_name
            )

            self.progress_updated.emit(100, "OCR processing completed!")
            self.ocr_completed.emit(validation_results, all_raw_responses)

        except Exception as e:
            logging.error(f"OCR processing thread failed: {e}")
            self.error_occurred.emit(str(e))


class EmployeeSearchDialog(QDialog):
    def __init__(self, validation_service: OCRValidationService, sheet_name: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.validation_service = validation_service
        self.sheet_name = sheet_name
        self.selected_employee = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Search Employee — Correction")
        self.setModal(True)
        self.resize(780, 550)

        layout = QVBoxLayout()

        # Sheet scope toggle
        scope_layout = QHBoxLayout()
        self.scope_toggle = QCheckBox("Active Sheet Only")
        self.scope_toggle.setChecked(True)
        self.scope_toggle.toggled.connect(self._on_scope_toggled)
        scope_layout.addWidget(self.scope_toggle)

        self.scope_label = QLabel(f"Sheet: {self.sheet_name}")
        self.scope_label.setStyleSheet("color: #666; font-style: italic;")
        scope_layout.addWidget(self.scope_label)
        scope_layout.addStretch()
        layout.addLayout(scope_layout)

        # Search input
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type employee ID or name")
        self.search_input.textChanged.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Count label
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #666; font-size: 9pt; margin-bottom: 2px;")
        layout.addWidget(self.count_label)

        # Results header
        header_label = QLabel(
            "  EMP ID   |  NAME                       |  SHEET          |  RANK"
        )
        header_label.setStyleSheet(
            "font-weight: bold; color: #333; padding: 2px 4px;"
        )
        layout.addWidget(header_label)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        self.results_list.itemDoubleClicked.connect(self.select_employee)
        layout.addWidget(self.results_list)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.select_employee)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _on_scope_toggled(self, active_only: bool):
        if active_only:
            self.scope_label.setText(f"Sheet: {self.sheet_name}")
        else:
            self.scope_label.setText("Showing all sheets")
        self.perform_search(self.search_input.text())

    def perform_search(self, query: str):
        self.results_list.clear()
        self.count_label.setText("")

        if len(query) < 1:
            return

        current_sheet = self.sheet_name if self.scope_toggle.isChecked() else None

        try:
            # Get total employee counts for diagnostics
            if current_sheet:
                total_in_sheet = len(self.validation_service.workbook_service.get_employees_by_sheet_as_objects(current_sheet))
                total_employees = self.validation_service.workbook_service.get_employee_count()
            else:
                total_employees = self.validation_service.workbook_service.get_employee_count()
                total_in_sheet = total_employees

            employees, total_matches = self.validation_service.search_employees_for_manual_match_with_count(
                query, sheet_name=current_sheet, limit=100
            )

            if len(employees) < total_matches:
                results_text = f"Showing {len(employees)} of {total_matches} results"
            else:
                results_text = f"Results: {len(employees)}"
                
            if not self.scope_toggle.isChecked():
                results_text += " (all sheets)"
            self.count_label.setText(results_text)

            # Log comprehensive search diagnostics
            logging.info(
                f"SEARCH_DIAGNOSTICS: "
                f"query='{query}' "
                f"active_sheet='{current_sheet or 'ALL'}' "
                f"employees_loaded={total_employees} "
                f"employees_filtered={total_in_sheet if current_sheet else total_employees} "
                f"results_displayed={len(employees)}"
            )

            # Auto-select first row for quick Enter key acceptance
            first_row = 0
            for i, emp in enumerate(employees):
                rank_text = emp.rank or ""
                item_text = (
                    f"  {emp.employee_id:8s} | {emp.name:28s} | "
                    f"{(emp.sheet_name or ''):14s} | {rank_text}"
                )
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, emp)
                self.results_list.addItem(item)

            if employees:
                self.results_list.setCurrentRow(0)

            logging.info(
                f"CORRECTION_SEARCH: UI "
                f"query='{query}' active_sheet='{self.sheet_name}' "
                f"mode={'active' if self.scope_toggle.isChecked() else 'all'} "
                f"returned={len(employees)}"
            )

        except Exception as e:
            logging.error(f"CORRECTION_SEARCH: UI error query='{query}': {e}")

    def select_employee(self):
        current_item = self.results_list.currentItem()
        if current_item:
            emp = current_item.data(Qt.UserRole)
            # Hard safety: verify sheet before applying
            if self.sheet_name:
                if emp.sheet_name != self.sheet_name:
                    QMessageBox.warning(
                        self,
                        "Sheet Mismatch",
                        f"Employee does not belong to the active worksheet.\n\n"
                        f"Employee '{emp.employee_id}' is in sheet '{emp.sheet_name}', "
                        f"but active sheet is '{self.sheet_name}'.\n\n"
                        f"Switch to 'All Sheets' mode to select cross-sheet employees."
                    )
                    return
            self.selected_employee = emp
            self.accept()
        else:
            QMessageBox.warning(
                self, "No Selection",
                "Please select an employee from the list."
            )

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.results_list.currentItem():
                self.select_employee()
                return
        super().keyPressEvent(event)


class VerificationWizard(QDialog):
    def __init__(self, validation_results: List[OCRValidationResult],
                 validation_service: OCRValidationService,
                 sheet_name: str, parent=None):
        super().__init__(parent)
        self.all_results = validation_results
        self.validation_service = validation_service
        self.sheet_name = sheet_name

        self.problem_rows = [
            r for r in self.all_results
            if r.status in (OCRStatus.UNMATCHED, OCRStatus.UNREADABLE)
        ]
        self.current_index = 0
        self.suggested_matches: List[Dict] = []

        self.setup_ui()
        self.show_current_record()

    def setup_ui(self):
        self.setWindowTitle("Verification Wizard")
        self.setModal(True)
        self.resize(700, 550)

        layout = QVBoxLayout()

        # Enhanced progress counter
        self.progress_label = QLabel()
        self.progress_label.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(self.progress_label)

        # Keyboard shortcuts help
        shortcuts_label = QLabel("Shortcuts: Enter=Accept+Next • Ctrl+Enter=Change Match • ←→=Navigate • Esc=Skip")
        shortcuts_label.setStyleSheet("color: #666; font-size: 9pt; font-style: italic; margin-bottom: 8px;")
        layout.addWidget(shortcuts_label)

        # OCR Data Card
        ocr_card = QFrame()
        ocr_card.setFrameStyle(QFrame.Box | QFrame.Raised)
        ocr_card.setStyleSheet("QFrame { background-color: #f8f8f8; padding: 16px; }")
        ocr_layout = QVBoxLayout(ocr_card)

        ocr_header = QLabel("OCR Data:")
        ocr_header.setFont(QFont("", 12, QFont.Bold))
        ocr_header.setStyleSheet("color: #333; margin-bottom: 4px;")
        ocr_layout.addWidget(ocr_header)

        self.ocr_id_label = QLabel()
        self.ocr_id_label.setFont(QFont("Courier", 18, QFont.Bold))
        self.ocr_id_label.setStyleSheet("color: #333;")
        ocr_layout.addWidget(self.ocr_id_label)

        self.ocr_name_label = QLabel()
        self.ocr_name_label.setFont(QFont("", 13))
        self.ocr_name_label.setStyleSheet("color: #555;")
        ocr_layout.addWidget(self.ocr_name_label)

        self.notes_label = QLabel()
        self.notes_label.setStyleSheet("color: #888; margin-top: 8px;")
        ocr_layout.addWidget(self.notes_label)

        layout.addWidget(ocr_card)

        # Live Preview Card (initially hidden)
        self.preview_card = QFrame()
        self.preview_card.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.preview_card.setStyleSheet("QFrame { background-color: #e8f5e8; padding: 16px; border: 2px solid #4CAF50; }")
        preview_layout = QVBoxLayout(self.preview_card)

        preview_header = QLabel("✓ Selected Employee:")
        preview_header.setFont(QFont("", 12, QFont.Bold))
        preview_header.setStyleSheet("color: #2E7D32; margin-bottom: 4px;")
        preview_layout.addWidget(preview_header)

        self.preview_id_label = QLabel()
        self.preview_id_label.setFont(QFont("Courier", 16, QFont.Bold))
        self.preview_id_label.setStyleSheet("color: #2E7D32;")
        preview_layout.addWidget(self.preview_id_label)

        self.preview_name_label = QLabel()
        self.preview_name_label.setFont(QFont("", 12))
        self.preview_name_label.setStyleSheet("color: #2E7D32;")
        preview_layout.addWidget(self.preview_name_label)

        self.preview_status_label = QLabel()
        self.preview_status_label.setFont(QFont("", 10, QFont.Bold))
        self.preview_status_label.setStyleSheet("color: #4CAF50; margin-top: 4px;")
        preview_layout.addWidget(self.preview_status_label)

        self.preview_card.setVisible(False)
        layout.addWidget(self.preview_card)

        self.match_group = QGroupBox("Suggested Matches")
        match_layout = QVBoxLayout()

        self.match_list = QListWidget()
        self.match_list.itemDoubleClicked.connect(self.accept_match)
        self.match_list.itemClicked.connect(lambda item: self.on_match_selection_changed(item, None))
        self.match_list.currentItemChanged.connect(self.on_match_selection_changed)
        match_layout.addWidget(self.match_list)

        self.no_match_label = QLabel("No suggestions found (exhausted all matching stages).")
        self.no_match_label.setStyleSheet("color: #D32F2F; padding: 8px; font-style: italic;")
        self.no_match_label.setVisible(False)
        match_layout.addWidget(self.no_match_label)

        self.match_group.setLayout(match_layout)
        layout.addWidget(self.match_group)

        btn_layout = QHBoxLayout()

        self.accept_btn = QPushButton("Accept Match")
        self.accept_btn.clicked.connect(self.accept_match)
        self.accept_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px;")
        btn_layout.addWidget(self.accept_btn)

        self.change_btn = QPushButton("Change Match")
        self.change_btn.clicked.connect(self.change_match)
        self.change_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 8px 16px;")
        btn_layout.addWidget(self.change_btn)

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.clicked.connect(self.skip_record)
        self.skip_btn.setStyleSheet("background-color: #9E9E9E; color: white; font-weight: bold; padding: 8px 16px;")
        btn_layout.addWidget(self.skip_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def show_current_record(self):
        # Enhanced progress counter
        remaining = len(self.problem_rows) - self.current_index
        total = len(self.problem_rows)
        current_num = self.current_index + 1
        reviewed = self.current_index
        
        self.progress_label.setText(
            f"Current Record: {current_num} / {total}  •  "
            f"Reviewed: {reviewed}  •  "
            f"Remaining: {remaining}"
        )

        if self.current_index >= len(self.problem_rows):
            self.accept()
            return

        result = self.problem_rows[self.current_index]

        self.ocr_id_label.setText(result.ocr_id)
        self.ocr_name_label.setText(result.ocr_name or "(no name detected)")
        self.notes_label.setText(result.validation_notes)

        # Update live preview based on current status
        if result.matched_employee:
            self.show_live_preview(result.matched_employee, "Manual Correction Applied")
        else:
            self.hide_live_preview()

        self.match_list.clear()
        self.no_match_label.setVisible(False)

        if result.status in (OCRStatus.UNMATCHED, OCRStatus.UNREADABLE):
            self.match_group.setVisible(True)
            self.suggested_matches = self.validation_service.find_possible_matches(
                result.ocr_id, result.ocr_name, self.sheet_name, limit=5
            )

            if self.suggested_matches:
                self.match_list.setVisible(True)
                self.no_match_label.setVisible(False)
                self.accept_btn.setEnabled(True)
                for m in self.suggested_matches:
                    emp = m["employee"]
                    score = m["score"]
                    m_type = m.get("match_type", "Fuzzy")
                    
                    # Display format: EMP_ID - NAME | TYPE [SCORE%]
                    text = f"{emp.employee_id} - {emp.name}\n   Match: {m_type}"
                    if "Other Sheet" in m_type:
                        text += f" | Sheet: {emp.sheet_name}"
                    
                    item = QListWidgetItem(text)
                    item.setData(Qt.UserRole, emp)
                    
                    # Tooltip for details
                    item.setToolTip(f"ID: {emp.employee_id}\nName: {emp.name}\nRank: {emp.rank}\nSheet: {emp.sheet_name}\nRow: {emp.row}")
                    
                    self.match_list.addItem(item)
                self.match_list.setCurrentRow(0)
            else:
                self.match_list.setVisible(False)
                self.no_match_label.setVisible(True)
                self.accept_btn.setEnabled(False)
        else:
            self.match_group.setVisible(False)
            self.no_match_label.setVisible(False)
            self.accept_btn.setEnabled(False)

    def show_live_preview(self, employee, status_text="Match Selected"):
        """Show live preview of selected employee."""
        self.preview_id_label.setText(employee.employee_id)
        self.preview_name_label.setText(f"{employee.name} ({employee.rank or 'No Rank'})")
        self.preview_status_label.setText(status_text)
        self.preview_card.setVisible(True)

    def hide_live_preview(self):
        """Hide live preview card."""
        self.preview_card.setVisible(False)

    def on_match_selection_changed(self, current, previous):
        """Show live preview when user selects a suggested match."""
        if current and current.data(Qt.UserRole):
            emp = current.data(Qt.UserRole)
            self.show_live_preview(emp, "Selected Match (Press Enter to Accept)")

    def accept_match(self):
        result = self.problem_rows[self.current_index]

        if self.suggested_matches and self.match_list.currentItem():
            emp = self.match_list.currentItem().data(Qt.UserRole)
            logging.info(
                f"SHEET_SCOPED: accept_match "
                f"employee={emp.employee_id} emp_sheet='{emp.sheet_name}' "
                f"active_sheet='{self.sheet_name}'"
            )
            self.validation_service.manual_correction(
                result, selected_employee=emp, sheet_name=self.sheet_name
            )

        self.current_index += 1
        self.show_current_record()

    def change_match(self):
        result = self.problem_rows[self.current_index]

        dialog = EmployeeSearchDialog(self.validation_service, sheet_name=self.sheet_name, parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_employee:
            emp = dialog.selected_employee
            logging.info(
                f"SHEET_SCOPED: change_match "
                f"employee={emp.employee_id} emp_sheet='{emp.sheet_name}' "
                f"active_sheet='{self.sheet_name}'"
            )
            
            # Apply manual correction
            self.validation_service.manual_correction(
                result, selected_employee=emp, sheet_name=self.sheet_name
            )
            
            # Immediately update UI to show the new match
            self.show_live_preview(emp, "Manual Correction Applied")
            
            # Update the notes to reflect the change
            self.notes_label.setText(f"Manually matched to {emp.employee_id} - {emp.name}")
            
            # Auto-advance to next record (configurable)
            if config.get_verification_auto_advance():
                self.current_index += 1
                self.show_current_record()

    def skip_record(self):
        result = self.problem_rows[self.current_index]
        result.is_checked = False
        result.checkbox_enabled = False
        self.current_index += 1
        self.show_current_record()

    def next_record(self):
        """Navigate to next record without accepting current match."""
        if self.current_index < len(self.problem_rows) - 1:
            self.current_index += 1
            self.show_current_record()

    def previous_record(self):
        """Navigate to previous record."""
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_record()

    def get_results(self) -> List[OCRValidationResult]:
        return self.all_results

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.change_match()
            return
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.accept_btn.isEnabled():
                self.accept_match()
            else:
                self.next_record()
            return
        elif event.key() == Qt.Key_Escape:
            self.skip_record()
            return
        elif event.key() == Qt.Key_Right:
            self.next_record()
            return
        elif event.key() == Qt.Key_Left:
            self.previous_record()
            return

        super().keyPressEvent(event)


class VerificationSummaryDialog(QDialog):
    def __init__(self, workbook_name: str, sheet_name: str, images_count: int,
                 total: int, confirmed: int, corrected: int, skipped: int,
                 shift: str, day: int, rows_to_mark: int,
                 ready_results: List = None, parent=None):
        super().__init__(parent)
        self.rows_to_mark = rows_to_mark
        self.ready_results = ready_results or []
        self.setup_ui(workbook_name, sheet_name, images_count, total, confirmed, corrected, skipped, shift, day)

    def setup_ui(self, workbook_name, sheet_name, images_count, total, confirmed, corrected, skipped, shift, day):
        self.setWindowTitle("Verification Summary")
        self.setModal(True)
        self.resize(600, 500)

        layout = QVBoxLayout()

        lines = [
            f"Workbook:  {workbook_name}",
            f"Target Sheet:  {sheet_name}",
            "",
            f"Images Processed:  {images_count}",
            f"Total OCR Records:  {total}",
            "",
            f"Confirmed:  {confirmed}",
            f"Corrected:  {corrected}",
            f"Skipped:  {skipped}",
            "",
            f"Date:  {day}",
            f"Shift:  {shift}",
            f"Rows To Mark:  {self.rows_to_mark}",
        ]

        for line in lines:
            if line == "":
                layout.addSpacing(4)
            else:
                label = QLabel(line)
                if line.startswith("Rows To Mark") or line.startswith("Shift") or line.startswith("Date"):
                    label.setFont(QFont("", 11, QFont.Bold))
                layout.addWidget(label)

        layout.addSpacing(8)

        # Employee list header
        emp_header = QLabel("Attendance Preview (Employee | Date | Shift | Target Sheet | Target Row):")
        emp_header.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(emp_header)

        # Scrollable employee list
        self.emp_list = QListWidget()
        self.emp_list.setMaximumHeight(200)
        for result in self.ready_results:
            emp = result.matched_employee
            if emp:
                corrected_mark = " [CORRECTED]" if result.manually_corrected else ""
                item_text = f"{emp.employee_id} - {emp.name}{corrected_mark} | Day {day} | Shift {shift} | Sheet: {emp.sheet_name} | Row: {emp.row}"
                self.emp_list.addItem(item_text)
        layout.addWidget(self.emp_list)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        self.proceed_btn = QPushButton("Proceed to Commit")
        self.proceed_btn.clicked.connect(self.accept)
        self.proceed_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 20px;")
        btn_layout.addWidget(self.proceed_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)


class PostCommitSummaryDialog(QDialog):
    def __init__(self, written: List[Dict], overwritten: List[Dict], skipped: List[Dict], errors: List[Dict],
                 workbook_info: Dict, parent=None):
        super().__init__(parent)
        self.written = written
        self.overwritten = overwritten
        self.skipped = skipped
        self.errors = errors
        self.workbook_info = workbook_info
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Commit Detailed Summary")
        self.setModal(True)
        self.resize(700, 600)

        layout = QVBoxLayout()

        # Header
        total_success = len(self.written) + len(self.overwritten)
        total_processed = total_success + len(self.skipped) + len(self.errors)
        
        header = QLabel("Commit Results Summary" if len(self.errors) == 0 else "Commit Completed with Issues")
        header.setFont(QFont("", 16, QFont.Bold))
        header.setStyleSheet("color: #2E7D32;" if len(self.errors) == 0 else "color: #C62828;")
        layout.addWidget(header)
        
        stats_row = QHBoxLayout()
        stats_row.addWidget(self._create_stat_widget("WRITTEN", len(self.written), "#4CAF50"))
        stats_row.addWidget(self._create_stat_widget("OVERWRITTEN", len(self.overwritten), "#2196F3"))
        stats_row.addWidget(self._create_stat_widget("SKIPPED", len(self.skipped), "#757575"))
        stats_row.addWidget(self._create_stat_widget("ERRORS", len(self.errors), "#F44336"))
        layout.addLayout(stats_row)

        layout.addSpacing(10)

        # Tabbed details
        self.tabs = QTabWidget()
        
        self.tabs.addTab(self._create_list_tab(self.written, "No records written."), "Written")
        self.tabs.addTab(self._create_overwritten_tab(), "Overwritten")
        self.tabs.addTab(self._create_list_tab(self.skipped, "No records skipped."), "Skipped")
        self.tabs.addTab(self._create_errors_tab(), "Errors")
        self.tabs.addTab(self._create_info_tab(), "Target Info")
        
        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        
        save_report_btn = QPushButton("Save Report")
        save_report_btn.setStyleSheet("padding: 8px 16px; background-color: #f0f0f0;")
        save_report_btn.clicked.connect(self.save_report)
        btn_layout.addWidget(save_report_btn)
        
        btn_layout.addStretch()
        
        ok_btn = QPushButton("Done")
        ok_btn.setStyleSheet("padding: 8px 32px; background-color: #4CAF50; color: white; font-weight: bold;")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _create_stat_widget(self, label, count, color):
        w = QWidget()
        l = QVBoxLayout(w)
        num = QLabel(str(count))
        num.setFont(QFont("", 18, QFont.Bold))
        num.setStyleSheet(f"color: {color};")
        num.setAlignment(Qt.AlignCenter)
        txt = QLabel(label)
        txt.setFont(QFont("", 9))
        txt.setAlignment(Qt.AlignCenter)
        l.addWidget(num)
        l.addWidget(txt)
        return w

    def _create_list_tab(self, records, empty_msg):
        if not records:
            return QLabel(empty_msg)
        
        list_widget = QListWidget()
        for r in records:
            list_widget.addItem(f"{r.get('employee_id', 'N/A')} - {r.get('employee_name', 'N/A')}")
        return list_widget

    def _create_overwritten_tab(self):
        if not self.overwritten:
            return QLabel("No records overwritten.")
        
        list_widget = QListWidget()
        for r in self.overwritten:
            item = f"{r.get('employee_id', 'N/A')} - {r.get('employee_name', 'N/A')}\n"
            item += f"    Previous: {r.get('old_value', 'empty')} -> New: {r.get('target_shift', 'N/A')}"
            list_widget.addItem(item)
        return list_widget

    def _create_errors_tab(self):
        if not self.errors:
            return QLabel("No errors occurred.")
        
        list_widget = QListWidget()
        for r in self.errors:
            item = f"{r.get('employee_id', 'N/A')} - {r.get('employee_name', 'N/A')}\n"
            item += f"    Error: {r.get('exception_type', 'Unknown')}\n"
            item += f"    Reason: {r.get('exception_message', 'N/A')}"
            list_widget.addItem(item)
        return list_widget

    def _create_info_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        info = QTextEdit()
        info.setReadOnly(True)
        
        lines = [
            "TARGET INFORMATION",
            "-------------------",
            f"Workbook:  {self.workbook_info.get('path', 'N/A')}",
            f"Sheet:     {self.workbook_info.get('sheet', 'N/A')}",
            f"Date:      {self.workbook_info.get('day', 'N/A')}",
            f"Shift:     {self.workbook_info.get('shift', 'N/A')}",
            "",
            "BATCH STATISTICS",
            "-------------------",
            f"Processed: {self.workbook_info.get('total', 0)}",
            f"Success:   {len(self.written) + len(self.overwritten)}",
            f"Failed:    {len(self.errors)}",
            f"Skipped:   {len(self.skipped)}"
        ]
        info.setText("\n".join(lines))
        l.addWidget(info)
        return w

    def save_report(self):
        try:
            report_path = "commit_report.txt"
            content = self._generate_report_text()
            
            with open(report_path, 'w') as f:
                f.write(content)
            
            QMessageBox.information(self, "Report Saved", f"Detailed report saved to {report_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save report: {e}")

    def _generate_report_text(self):
        lines = []
        lines.append("---------------------------------------")
        lines.append("COMMIT SUMMARY")
        lines.append("---------------------------------------")
        lines.append(f"Written:     {len(self.written)}")
        lines.append(f"Overwritten: {len(self.overwritten)}")
        lines.append(f"Skipped:     {len(self.skipped)}")
        lines.append(f"Errors:      {len(self.errors)}")
        lines.append("")
        
        if self.written:
            lines.append("---------------------------------------")
            lines.append("WRITTEN")
            lines.append("---------------------------------------")
            for r in self.written:
                lines.append(f"{r.get('employee_id', 'N/A')} - {r.get('employee_name', 'N/A')}")
            lines.append("")
            
        if self.overwritten:
            lines.append("---------------------------------------")
            lines.append("OVERWRITTEN")
            lines.append("---------------------------------------")
            for r in self.overwritten:
                lines.append(f"{r.get('employee_id', 'N/A')} - {r.get('employee_name', 'N/A')}")
                lines.append(f"    Previous: {r.get('old_value', 'empty')}")
                lines.append(f"    New:      {r.get('target_shift', 'N/A')}")
            lines.append("")
            
        if self.skipped:
            lines.append("---------------------------------------")
            lines.append("SKIPPED")
            lines.append("---------------------------------------")
            for r in self.skipped:
                lines.append(f"{r.get('employee_id', 'N/A')} - {r.get('employee_name', 'N/A')}")
                lines.append(f"    Reason: User selected Skip")
            lines.append("")
            
        if self.errors:
            lines.append("---------------------------------------")
            lines.append("ERRORS")
            lines.append("---------------------------------------")
            for r in self.errors:
                lines.append(f"{r.get('employee_id', 'N/A')} - {r.get('employee_name', 'N/A')}")
                lines.append(f"    Error: {r.get('exception_type', 'Unknown')}")
                lines.append(f"    Reason: {r.get('exception_message', 'N/A')}")
            lines.append("")
            
        lines.append("---------------------------------------")
        lines.append("TARGET INFORMATION")
        lines.append("---------------------------------------")
        lines.append(f"Workbook:  {self.workbook_info.get('path', 'N/A')}")
        lines.append(f"Sheet:     {self.workbook_info.get('sheet', 'N/A')}")
        lines.append(f"Date:      {self.workbook_info.get('day', 'N/A')}")
        lines.append(f"Shift:     {self.workbook_info.get('shift', 'N/A')}")
        lines.append(f"Processed: {self.workbook_info.get('total', 0)}")
        lines.append(f"Success:   {len(self.written) + len(self.overwritten)}")
        lines.append(f"Failed:    {len(self.errors)}")
        lines.append("---------------------------------------")
        
        return "\n".join(lines)


class OCRAttendanceTab(QWidget):
    def __init__(self, workbook_service: WorkbookService, attendance_service: AttendanceService,
                 main_window=None):
        super().__init__()
        self.workbook_service = workbook_service
        self.attendance_service = attendance_service
        self.main_window = main_window

        self.ocr_service = None
        self.validation_service = OCRValidationService(workbook_service)

        self.validation_results: List[OCRValidationResult] = []
        self.current_images: List[str] = []
        self.ocr_enabled = False

        self.setup_ui()
        self.setup_connections()
        self.initialize_ocr_service()
        # Attempt initial model discovery from provider
        if config.has_valid_api_key():
            try:
                self._refresh_models()
            except Exception as e:
                logging.warning(f"Initial model discovery failed: {e}")
                # User can use Refresh Models button to retry

    def setup_ui(self):
        main_layout = QVBoxLayout()

        header_group = QGroupBox("OCR Attendance Processing")
        header_layout = QVBoxLayout()

        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Ready to process images")
        self.stats_label.setFont(QFont("", 10, QFont.Bold))
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()

        self.api_status_label = QLabel("Gemini API: Not initialized")
        stats_layout.addWidget(self.api_status_label)
        header_layout.addLayout(stats_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        header_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        header_layout.addWidget(self.status_label)

        active_sheet = self.main_window.active_sheet_name if self.main_window else "(none)"
        self.active_sheet_label = QLabel(f"Active Sheet: {active_sheet}")
        self.active_sheet_label.setStyleSheet("color: #555; font-weight: bold;")
        header_layout.addWidget(self.active_sheet_label)

        # Model selection row
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(280)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_layout.addWidget(self.model_combo)

        self.refresh_models_btn = QPushButton("Refresh Models")
        self.refresh_models_btn.clicked.connect(self._refresh_models)
        self.refresh_models_btn.setStyleSheet("font-size: 9pt; padding: 2px 8px;")
        model_layout.addWidget(self.refresh_models_btn)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_connection)
        model_layout.addWidget(self.test_btn)

        self.conn_status_label = QLabel("")
        self.conn_status_label.setStyleSheet("font-size: 9pt;")
        model_layout.addWidget(self.conn_status_label)
        model_layout.addStretch()
        header_layout.addLayout(model_layout)

        header_group.setLayout(header_layout)
        main_layout.addWidget(header_group)

        upload_group = QGroupBox("Step 1: Upload Images")
        upload_layout = QHBoxLayout()

        self.browse_button = QPushButton("Add Images")
        self.browse_button.clicked.connect(self.browse_images)
        upload_layout.addWidget(self.browse_button)

        upload_layout.addStretch()

        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_all)
        upload_layout.addWidget(self.clear_button)

        upload_group.setLayout(upload_layout)
        main_layout.addWidget(upload_group)

        self.files_label = QLabel("No images selected")
        main_layout.addWidget(self.files_label)

        process_group = QGroupBox("Step 2: OCR Processing")
        process_layout = QHBoxLayout()

        self.process_button = QPushButton("Process Images")
        self.process_button.clicked.connect(self.process_images)
        self.process_button.setEnabled(False)
        process_layout.addWidget(self.process_button)

        process_layout.addStretch()
        process_group.setLayout(process_layout)
        main_layout.addWidget(process_group)

        verify_group = QGroupBox("Step 3: Verification")
        verify_layout = QHBoxLayout()

        self.verify_button = QPushButton("Start Verification")
        self.verify_button.clicked.connect(self.start_verification)
        self.verify_button.setEnabled(False)
        self.verify_button.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px 20px;")
        verify_layout.addWidget(self.verify_button)

        verify_layout.addStretch()
        self.verify_status_label = QLabel("Process images to begin verification")
        verify_layout.addWidget(self.verify_status_label)

        verify_group.setLayout(verify_layout)
        main_layout.addWidget(verify_group)

        commit_group = QGroupBox("Step 4: Commit to Workbook")
        commit_layout = QHBoxLayout()

        commit_layout.addWidget(QLabel("Date:"))
        self.update_available_dates()
        commit_layout.addWidget(self.date_combo)

        commit_layout.addWidget(QLabel("Shift:"))
        self.shift_combo = QComboBox()
        self.shift_combo.addItems(["", "A", "B", "C", "G", "WO", "AB"])
        self.shift_combo.setCurrentText("A")
        self.shift_combo.setMinimumWidth(80)
        commit_layout.addWidget(self.shift_combo)

        commit_layout.addStretch()

        self.save_button = QPushButton("Save To Workbook")
        self.save_button.clicked.connect(self.commit_to_excel)
        self.save_button.setEnabled(False)
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 20px;")
        commit_layout.addWidget(self.save_button)

        commit_group.setLayout(commit_layout)
        main_layout.addWidget(commit_group)

        debug_group = QGroupBox("Raw OCR Output (Advanced)")
        debug_layout = QVBoxLayout()

        self.raw_response_text = QTextEdit()
        self.raw_response_text.setMaximumHeight(120)
        self.raw_response_text.setReadOnly(True)
        debug_layout.addWidget(self.raw_response_text)

        debug_group.setLayout(debug_layout)
        main_layout.addWidget(debug_group)

        self.setLayout(main_layout)

    def setup_connections(self):
        self.shift_combo.currentTextChanged.connect(self.update_commit_readiness)

    def initialize_ocr_service(self):
        has_key = config.has_valid_api_key()
        logging.info(f"=== OCR Startup Diagnostics ===")
        logging.info(f"Config file found: True")
        logging.info(f"API key configured: {config.has_valid_api_key()}")
        logging.info(f"OCR enabled: {config.has_valid_api_key()}")
        logging.info(f"==================================")

        if config.has_valid_api_key():
            try:
                self.ocr_service = OCRService(
                    config.get_gemini_api_key(),
                    model=self.model_combo.currentText() if hasattr(self, 'model_combo') else None
                )
                self.ocr_enabled = True
                self.api_status_label.setText("Gemini API: Ready")
                self.api_status_label.setStyleSheet("color: green;")
                self._enable_ocr_controls(True)
                logging.info("OCR service initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize OCR service: {e}")
                self.api_status_label.setText("Gemini API: Error")
                self.api_status_label.setStyleSheet("color: red;")
                self._enable_ocr_controls(False)
        else:
            self.ocr_enabled = False
            self.api_status_label.setText("Gemini API: Not Configured")
            self.api_status_label.setStyleSheet("color: orange;")
            self._enable_ocr_controls(False)
            self._add_configure_button()
            logging.info("OCR disabled: No API key configured")

    def _on_model_changed(self, text: str):
        """Handle model selection or manual entry."""
        # Get the raw model name using the helper method
        actual = self._get_current_raw_model_name()
        
        if not actual:
            return

        logging.info(f"MODEL_FORMAT_DEBUG: Model changed")
        logging.info(f"  Display text: '{text}'")
        logging.info(f"  Raw model name: '{actual}'")
        
        config.set_gemini_model(actual)
        logging.info(f"Model saved to config: {actual}")
        self.conn_status_label.setText("")
        if self.ocr_service:
            self.ocr_service = OCRService(
                api_key=config.get_gemini_api_key(),
                model=actual
            )

    def _refresh_models(self):
        """Re-query provider and repopulate the model dropdown."""
        if not config.has_valid_api_key():
            QMessageBox.warning(self, "API Key Required",
                                "Configure a valid API key before refreshing models.")
            return

        self.refresh_models_btn.setEnabled(False)
        self.conn_status_label.setText("Fetching models...")
        self.conn_status_label.setStyleSheet("color: #666; font-size: 9pt;")

        try:
            from services.gemini_client import GeminiClient
            client = GeminiClient()
            models = client.list_models()

            # Remember previously selected model from config
            previous_model = config.get_gemini_model()

            self.model_combo.blockSignals(True)
            self.model_combo.clear()

            if models:
                for m in models:
                    label = "Vision" if m.get('supports_vision', False) else "Text Only"
                    display_name = m.get('display_name', m['name'])
                    friendly_text = f"{display_name}"
                    api_name = m['name']
                    display_text = f"{friendly_text} ({api_name}) ({label})"
                    
                    # Store raw API identifier as user data
                    self.model_combo.addItem(display_text, api_name)
                    idx = self.model_combo.count() - 1
                    self.model_combo.setItemData(
                        idx, m.get('supports_vision', False), Qt.UserRole + 1
                    )
                    self.model_combo.setItemData(
                        idx, label, Qt.ToolTipRole
                    )

                # Try to restore previous selection
                target_raw = previous_model
                target_norm = GeminiClient.normalize_model_name(previous_model) if previous_model else None
                
                idx = self.model_combo.findData(target_raw)
                if idx < 0 and target_norm:
                    # Try normalized version for backward compat with old config format
                    for i in range(self.model_combo.count()):
                        data = self.model_combo.itemData(i)
                        if isinstance(data, str) and GeminiClient.normalize_model_name(data) == target_norm:
                            idx = i
                            break
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)

                logging.info(f"MODEL_DISCOVERY: Total Models Returned: {len(models)}")
                logging.info(f"MODEL_DISCOVERY: Total Models Displayed: {self.model_combo.count()}")
                self.conn_status_label.setText(f"Loaded {self.model_combo.count()} models")
                self.conn_status_label.setStyleSheet("color: green; font-size: 9pt;")
            else:
                self.model_combo.addItem(
                    config.get_gemini_model() or "Enter model name",
                    config.get_gemini_model()
                )
                logging.warning("MODEL_DISCOVERY: Provider returned 0 models")
                self.conn_status_label.setText("No models returned — enter manually")
                self.conn_status_label.setStyleSheet("color: orange; font-size: 9pt;")

        except Exception as e:
            logging.error(f"MODEL_DISCOVERY: Failed to refresh models: {e}")
            self.conn_status_label.setText(f"Error: {e}")
            self.conn_status_label.setStyleSheet("color: red; font-size: 9pt;")
            if self.model_combo.count() == 0:
                default = config.get_gemini_model() or "Enter model name"
                self.model_combo.addItem(default, config.get_gemini_model())
        finally:
            self.model_combo.blockSignals(False)
            self.refresh_models_btn.setEnabled(True)

    def _test_connection(self):
        if not self.ocr_service:
            QMessageBox.warning(self, "OCR Not Initialized",
                                "OCR service is not available. Check API key.")
            return
        self.test_btn.setEnabled(False)
        self.conn_status_label.setText("Testing...")
        
        # Get the raw model name (not display text)
        raw_model = self._get_current_raw_model_name()
        logging.info(f"MODEL_FORMAT_DEBUG: Test Connection using model: '{raw_model}'")
        
        # Run test synchronously (fast operation, no thread needed)
        result = self.ocr_service.test_connection(model=raw_model)
        self.test_btn.setEnabled(True)
        if result["success"]:
            self.conn_status_label.setText(
                f"OK — {result['latency']:.1f}s — {result['model']}"
            )
            self.conn_status_label.setStyleSheet("color: green; font-size: 9pt;")
        else:
            # Enhanced error message for model format issues
            error_msg = result.get('error', 'unknown error')
            if "INVALID_ARGUMENT" in error_msg and "model" in error_msg.lower():
                detailed_msg = f"Model Format Error\nRaw: {raw_model}\nError: {error_msg}"
                self.conn_status_label.setText(detailed_msg)
            else:
                self.conn_status_label.setText(f"FAIL — {error_msg}")
            self.conn_status_label.setStyleSheet("color: red; font-size: 9pt;")

    def _get_current_raw_model_name(self) -> str:
        """Get the raw model name (API identifier) from current selection."""
        idx = self.model_combo.currentIndex()
        if idx >= 0:
            # Try to get raw model name from item data
            data = self.model_combo.itemData(idx)
            if isinstance(data, str) and data:
                return data
        
        # Fall back to current text (manual entry or no data available)
        text = self.model_combo.currentText()
        
        # Strip metadata label if present (e.g., "gemini-2.5-flash (Vision)" -> "gemini-2.5-flash")
        if text and ' (' in text and text.endswith(')'):
            parts = text.rsplit(' (', 1)
            if len(parts) == 2:
                return parts[0]
        
        return text

    def _enable_ocr_controls(self, enabled: bool):
        self.ocr_enabled = enabled
        self.process_button.setEnabled(enabled and len(self.current_images) > 0)
        self.browse_button.setEnabled(enabled)
        if hasattr(self, 'configure_btn') and self.configure_btn:
            self.configure_btn.setVisible(not enabled)

    def _add_configure_button(self):
        if hasattr(self, 'configure_btn') and self.configure_btn:
            return

        self.configure_btn = QPushButton("Configure Gemini API Key")
        self.configure_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 8px 16px;")
        self.configure_btn.clicked.connect(self._configure_api_key)

        for child in self.children():
            if isinstance(child, QGroupBox) and child.title() == "OCR Attendance Processing":
                layout = child.layout()
                if layout and layout.count() > 0:
                    stats_layout = layout.itemAt(0).layout() if layout.itemAt(0) else None
                    if stats_layout:
                        stats_layout.addWidget(self.configure_btn)
                        break

    def _configure_api_key(self):
        from ui.api_key_dialog import FirstLaunchManager
        manager = FirstLaunchManager(self)
        if manager.show_reconfigure_dialog():
            self.initialize_ocr_service()

    def browse_images(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Attendance Images",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
        )

        if file_paths:
            self.current_images = file_paths
            self.update_files_display()
            self.process_button.setEnabled(self.ocr_enabled)

    def update_files_display(self):
        if not self.current_images:
            self.files_label.setText("No images selected")
            return

        if len(self.current_images) == 1:
            filename = Path(self.current_images[0]).name
            self.files_label.setText(f"Selected: {filename}")
        else:
            filenames = [Path(path).name for path in self.current_images]
            self.files_label.setText(f"Selected {len(self.current_images)} files: " +
                                   ", ".join(filenames[:3]) +
                                   ("..." if len(filenames) > 3 else ""))

    def process_images(self):
        if not self.current_images:
            QMessageBox.warning(self, "No Images", "Please select images to process.")
            return

        if not self.ocr_enabled or not self.ocr_service:
            QMessageBox.warning(self, "OCR Not Configured",
                              "Please configure your Gemini API key first using the 'Configure Gemini API Key' button.")
            return

        active_sheet = self.main_window.active_sheet_name if self.main_window else None
        if not active_sheet:
            QMessageBox.warning(self, "No Active Sheet",
                              "Please select an active sheet in the main window before processing.")
            return

        self.validation_results.clear()
        self.raw_response_text.clear()

        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.progress_bar.setValue(0)

        self.process_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.model_combo.setEnabled(False)  # Lock model during processing
        self.refresh_models_btn.setEnabled(False)

        self.ocr_thread = OCRProcessingThread(
            self.current_images,
            self.ocr_service,
            self.validation_service,
            sheet_name=active_sheet
        )
        self.ocr_thread.progress_updated.connect(self.update_progress)
        self.ocr_thread.ocr_completed.connect(self.handle_ocr_completed)
        self.ocr_thread.error_occurred.connect(self.handle_ocr_error)
        self.ocr_thread.start()

    def update_progress(self, percentage: int, message: str):
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)

    def handle_ocr_completed(self, validation_results: List[OCRValidationResult],
                           raw_responses: List[str]):
        self.validation_results = validation_results
        self.update_statistics()

        self.raw_response_text.setText("\n\n".join(raw_responses))

        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        self.process_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.model_combo.setEnabled(True)  # Unlock model after processing
        self.refresh_models_btn.setEnabled(True)

        self.verify_button.setEnabled(True)
        self.verify_status_label.setText(f"{len(validation_results)} records extracted. Click to review.")

    def handle_ocr_error(self, error_message: str):
        QMessageBox.critical(self, "OCR Processing Error",
                           f"OCR processing failed:\n{error_message}")

        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        self.process_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.model_combo.setEnabled(True)  # Unlock model after error
        self.refresh_models_btn.setEnabled(True)

    def start_verification(self):
        if not self.validation_results:
            return

        active_sheet = self.main_window.active_sheet_name if self.main_window else None
        if not active_sheet:
            QMessageBox.warning(self, "No Active Sheet",
                              "Please select an active sheet first.")
            return

        wizard = VerificationWizard(
            self.validation_results,
            self.validation_service,
            active_sheet,
            parent=self
        )
        wizard.exec()

        self.validation_results = wizard.get_results()
        self.update_statistics()
        self.update_commit_readiness()

        # Show verification summary
        stats = self.validation_service.get_validation_statistics()
        corrected = sum(1 for r in self.validation_results if r.manually_corrected)
        skipped = sum(1 for r in self.validation_results if not r.is_checked)
        ready = len(self.validation_service.filter_ready_for_commit(self.validation_results))

        summary_lines = [
            f"Total Records:  {stats['total_processed']}",
            f"Confirmed:  {stats['confirmed']}",
            f"Manually Corrected:  {corrected}",
            f"Skipped:  {skipped}",
            f"Unmatched:  {stats['unmatched']}",
            f"Unreadable:  {stats['unreadable']}",
            "",
            f"Ready to Commit:  {ready}",
        ]
        QMessageBox.information(
            self, "Verification Complete",
            "\n".join(summary_lines)
        )

    def update_statistics(self):
        if not self.validation_results:
            self.stats_label.setText("Ready to process images")
            return

        stats = self.validation_service.get_validation_statistics()

        self.stats_label.setText(
            f"Total: {stats['total_processed']} | "
            f"Confirmed: {stats['confirmed']} | "
            f"Unmatched: {stats['unmatched']} | "
            f"Unreadable: {stats['unreadable']}"
        )

    def update_commit_readiness(self):
        shift = self.shift_combo.currentText()
        if not shift:
            self.save_button.setEnabled(False)
            self.verify_status_label.setText("Select a shift to enable Save To Workbook")
            return

        ready = self.validation_service.filter_ready_for_commit(self.validation_results)
        if ready:
            self.save_button.setEnabled(True)
            self.verify_status_label.setText(f"{len(ready)} records ready to commit")
        else:
            self.save_button.setEnabled(False)
            self.verify_status_label.setText("No confirmed records ready for commit")

    def commit_to_excel(self):
        logging.info("=== COMMIT FLOW START ===")
        logging.info(f"Current model: {self.model_combo.currentText()}")
        idx = self.model_combo.currentIndex()
        if idx >= 0:
            supports_vision = self.model_combo.itemData(idx, Qt.UserRole + 1)
            logging.info(f"Model supports vision: {supports_vision}")
        
        ready_results, warnings = self.validation_service.validate_commit_readiness(
            self.validation_results
        )

        if not ready_results:
            QMessageBox.warning(self, "Nothing to Commit",
                              "No rows are ready for commit.\n\n" +
                              ("\n".join(warnings) if warnings else ""))
            return

        shift = self.shift_combo.currentText()
        if not shift:
            QMessageBox.warning(self, "No Shift Selected",
                              "Please select a shift before committing.")
            return

        day = int(self.date_combo.currentText())

        active_sheet = self.main_window.active_sheet_name if self.main_window else None
        workbook_name = Path(self.main_window.workbook_path).name if self.main_window else "(unknown)"

        stats = self.validation_service.get_validation_statistics()
        corrected = sum(1 for r in self.validation_results if r.manually_corrected)
        skipped = sum(1 for r in self.validation_results if not r.is_checked)

        summary = VerificationSummaryDialog(
            workbook_name=workbook_name,
            sheet_name=active_sheet,
            images_count=len(self.current_images),
            total=stats['total_processed'],
            confirmed=stats['confirmed'],
            corrected=corrected,
            skipped=skipped,
            shift=shift,
            day=day,
            rows_to_mark=len(ready_results),
            ready_results=ready_results,
            parent=self
        )

        if summary.exec() != QDialog.Accepted:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Save",
            f"{len(ready_results)} attendance records will be written to {active_sheet} sheet.\n\n"
            f"Date: {day} | Shift: {shift}\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self._perform_commit(ready_results, day, shift, active_sheet)

    def _perform_commit(self, ready_results: List[OCRValidationResult], day: int, shift: str, active_sheet: str):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Writing to workbook...")

        self.save_button.setEnabled(False)
        self.verify_button.setEnabled(False)
        self.model_combo.setEnabled(False)  # Lock model during commit
        self.refresh_models_btn.setEnabled(False)

        total = len(ready_results)
        
        # Categorized lists for summary
        written_list = []
        overwritten_list = []
        error_list = []
        skipped_list = []
        
        # Collect explicitly skipped (unchecked) records
        for res in self.validation_results:
            if not res.is_checked:
                skipped_list.append({
                    'employee_id': res.ocr_id,
                    'employee_name': res.ocr_name,
                    'reason': 'User selected Skip'
                })

        for i, result in enumerate(ready_results):
            emp = result.matched_employee
            try:
                old_value = self.attendance_service.mark(
                    emp,
                    day,
                    shift,
                    active_sheet
                )

                record_data = {
                    'employee_id': emp.employee_id,
                    'employee_name': emp.name,
                    'old_value': old_value,
                    'target_shift': shift
                }

                if old_value is not None and old_value != "":
                    overwritten_list.append(record_data)
                else:
                    written_list.append(record_data)

                self.progress_bar.setValue(int((i + 1) / total * 100))
                self.status_label.setText(f"Writing record {i + 1}/{total}...")

            except Exception as e:
                # Capture comprehensive failure details
                target_col = 'N/A'
                if emp and hasattr(self.attendance_service, 'dates'):
                    dates = self.attendance_service.dates
                    if isinstance(dates, dict):
                        if emp.sheet_name in dates:
                            target_col = dates[emp.sheet_name].get(day, 'N/A')
                        elif day in dates:
                            target_col = dates.get(day, 'N/A')

                failure_detail = {
                    'employee_id': emp.employee_id if emp else 'N/A',
                    'employee_name': emp.name if emp else 'N/A',
                    'employee_sheet': emp.sheet_name if emp else 'N/A',
                    'active_sheet': active_sheet or 'N/A',
                    'target_day': day,
                    'target_shift': shift,
                    'target_row': emp.row if emp else 'N/A',
                    'target_column': target_col,
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'ocr_id': result.ocr_id,
                    'ocr_name': result.ocr_name
                }
                error_list.append(failure_detail)
                
                logging.error(f"COMMIT FAILURE: {failure_detail['employee_id']} - {failure_detail['exception_message']}")

        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        self.save_button.setEnabled(True)
        self.verify_button.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.refresh_models_btn.setEnabled(True)

        success_count = len(written_list) + len(overwritten_list)
        error_count = len(error_list)

        # Generate failure report MD if errors occurred
        if error_count > 0:
            self._generate_commit_failure_report(error_list, success_count, error_count, total)
            if success_count == 0:
                first_failure = error_list[0]
                QMessageBox.critical(
                    self, "Critical Commit Failure",
                    f"All {total} records failed to write!\n\n"
                    f"First Failure:\n"
                    f"Employee: {first_failure.get('employee_id', 'N/A')}\n"
                    f"Error: {first_failure.get('exception_message', 'N/A')}"
                )

        # Auto-save workbook if any success
        try:
            if self.main_window and success_count > 0:
                self.attendance_service.save(self.main_window.workbook_path)
                logging.info(f"OCR COMMIT: Workbook saved ({success_count} records)")
        except Exception as e:
            logging.error(f"OCR COMMIT: Failed to save workbook: {e}")
            QMessageBox.warning(self, "Save Warning", f"Records written but workbook could not be auto-saved: {e}")

        # Show detailed summary dialog
        workbook_info = {
            'path': os.path.basename(self.main_window.workbook_path) if self.main_window else "N/A",
            'sheet': active_sheet,
            'day': day,
            'shift': shift,
            'total': total + len(skipped_list)
        }
        
        dialog = PostCommitSummaryDialog(
            written=written_list,
            overwritten=overwritten_list,
            skipped=skipped_list,
            errors=error_list,
            workbook_info=workbook_info,
            parent=self
        )
        dialog.exec()

        # Cleanup
        self.validation_results = [r for r in self.validation_results if r not in ready_results]
        self.update_statistics()
        self.update_commit_readiness()

    def _generate_commit_failure_report(self, failed_records: List[Dict], success_count: int, error_count: int, total: int):
        """Generate detailed commit failure report."""
        from datetime import datetime
        
        report_path = Path("COMMIT_FAILURE_REPORT.md")
        
        with open(report_path, 'w') as f:
            f.write("# Commit Failure Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"## Summary\n\n")
            f.write(f"- **Total Records:** {total}\n")
            f.write(f"- **Successfully Written:** {success_count}\n")
            f.write(f"- **Failed:** {error_count}\n")
            f.write(f"- **Success Rate:** {(success_count/total*100):.1f}%\n\n")
            
            if self.main_window:
                f.write(f"**Workbook:** {self.main_window.workbook_path}\n")
                f.write(f"**Active Sheet:** {self.main_window.active_sheet_name}\n\n")
            
            # Analyze failure patterns
            f.write("## Failure Analysis\n\n")
            exception_types = {}
            for record in failed_records:
                exc_type = record.get('exception_type', 'Unknown')
                exception_types[exc_type] = exception_types.get(exc_type, 0) + 1
            
            f.write("### Exception Types\n\n")
            for exc_type, count in sorted(exception_types.items(), key=lambda x: x[1], reverse=True):
                f.write(f"- **{exc_type}:** {count} occurrences ({count/error_count*100:.1f}%)\n")
            f.write("\n")
            
            # Detailed failure records (first 10)
            f.write("## Detailed Failure Records (First 10)\n\n")
            for i, record in enumerate(failed_records[:10], 1):
                f.write(f"### Failure #{i}\n\n")
                f.write(f"**Employee Information:**\n")
                f.write(f"- Employee ID: `{record.get('employee_id', 'N/A')}`\n")
                f.write(f"- Employee Name: `{record.get('employee_name', 'N/A')}`\n")
                f.write(f"- Employee Sheet: `{record.get('employee_sheet', 'N/A')}`\n")
                f.write(f"- Target Row: `{record.get('target_row', 'N/A')}`\n\n")
                
                f.write(f"**Write Target:**\n")
                f.write(f"- Active Sheet: `{record.get('active_sheet', 'N/A')}`\n")
                f.write(f"- Target Day: `{record.get('target_day', 'N/A')}`\n")
                f.write(f"- Target Shift: `{record.get('target_shift', 'N/A')}`\n")
                f.write(f"- Target Column: `{record.get('target_column', 'N/A')}`\n\n")
                
                f.write(f"**OCR Data:**\n")
                f.write(f"- OCR ID: `{record.get('ocr_id', 'N/A')}`\n")
                f.write(f"- OCR Name: `{record.get('ocr_name', 'N/A')}`\n\n")
                
                f.write(f"**Exception:**\n")
                f.write(f"```\n")
                f.write(f"{record.get('exception_type', 'Unknown')}: {record.get('exception_message', 'N/A')}\n")
                f.write(f"```\n\n")
            
            # Root cause analysis
            f.write("## Root Cause Analysis\n\n")
            
            # Check for common patterns
            if 'KeyError' in exception_types:
                f.write("### KeyError Issues\n")
                f.write("- **Likely Cause:** Date column not found in date index\n")
                f.write("- **Check:** Verify that the selected date exists in the workbook's date row\n")
                f.write("- **Fix:** Ensure date indexing is correct and target day matches workbook structure\n\n")
            
            if 'ValueError' in exception_types:
                # Check if sheet mismatch
                sheet_mismatches = [r for r in failed_records if 'Sheet mismatch' in r.get('exception_message', '')]
                if sheet_mismatches:
                    f.write("### Sheet Mismatch\n")
                    f.write(f"- **Affected Records:** {len(sheet_mismatches)}\n")
                    f.write("- **Cause:** Employees belong to different sheet than active sheet\n")
                    f.write("- **Fix:** This should not happen - indicates a validation bug\n\n")
            
            if 'AttributeError' in exception_types:
                f.write("### AttributeError Issues\n")
                f.write("- **Likely Cause:** Missing employee data or invalid workbook structure\n")
                f.write("- **Check:** Verify employee objects have all required attributes (row, sheet_name, employee_id)\n\n")
            
            # Recommendations
            f.write("## Recommended Actions\n\n")
            f.write("1. Review the detailed failure records above\n")
            f.write("2. Check `attenist.log` for full stack traces\n")
            f.write("3. Verify workbook structure matches expected format\n")
            f.write("4. Ensure date indexing captured the correct date columns\n")
            f.write("5. Confirm active sheet matches employee data\n")
            f.write("6. If all records failed, this indicates a systemic issue, not individual record problems\n\n")
            
            if error_count > 10:
                f.write(f"## Additional Failures\n\n")
                f.write(f"**Note:** {error_count - 10} additional failures not shown in detail. ")
                f.write(f"Check the log file for complete information.\n\n")
        
        logging.info(f"COMMIT_DIAGNOSTICS: Failure report written to {report_path}")

    def refresh_sheet(self) -> bool:
        """Returns True if sheet change is allowed, False if cancelled by user."""
        if self.validation_results or self.current_images:
            reply = QMessageBox.question(
                self,
                "Sheet Changed",
                "The active sheet has changed. This will clear current OCR results. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return False

            self.validation_results.clear()
            self.current_images.clear()
            self.raw_response_text.clear()
            self.update_files_display()
            self.stats_label.setText("Ready to process images")
            self.verify_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.process_button.setEnabled(self.ocr_enabled)
            self.verify_status_label.setText("Process images to begin verification")

        active_sheet = self.main_window.active_sheet_name if self.main_window else "(none)"
        self.active_sheet_label.setText(f"Active Sheet: {active_sheet}")
        
        # Refresh dates for the new sheet
        self.update_available_dates()
        return True

    def update_available_dates(self):
        """Update date_combo with available days for the current active sheet."""
        if not hasattr(self, 'date_combo'):
            self.date_combo = QComboBox()
            
        self.date_combo.clear()
        
        active_sheet = self.main_window.active_sheet_name if self.main_window else None
        dates_dict = self.attendance_service.dates
        
        if not dates_dict or not active_sheet:
            # Fallback to 1-31 if no indexing info
            self.date_combo.addItems([str(d) for d in range(1, 32)])
        else:
            # Handle per-sheet structure
            sheet_dates = {}
            if active_sheet in dates_dict:
                sheet_dates = dates_dict[active_sheet]
            elif any(not isinstance(v, dict) for v in dates_dict.values()):
                # Global structure
                sheet_dates = dates_dict
                
            if sheet_dates:
                available_days = sorted(sheet_dates.keys())
                self.date_combo.addItems([str(day) for day in available_days])
            else:
                # Still fallback to 1-31 if this sheet has no dates
                self.date_combo.addItems([str(d) for d in range(1, 32)])

        # Try to select current day as default
        from datetime import datetime
        current_day = str(datetime.now().day)
        index = self.date_combo.findText(current_day)
        if index >= 0:
            self.date_combo.setCurrentIndex(index)
        elif self.date_combo.count() > 0:
            self.date_combo.setCurrentIndex(0)

    def clear_all(self):
        reply = QMessageBox.question(self, "Clear All Data",
                                   "This will clear all OCR results and selected images. Continue?",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.validation_results.clear()
            self.current_images.clear()
            self.raw_response_text.clear()
            self.update_files_display()
            self.stats_label.setText("Ready to process images")
            self.verify_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.process_button.setEnabled(self.ocr_enabled)
            self.verify_status_label.setText("Process images to begin verification")
