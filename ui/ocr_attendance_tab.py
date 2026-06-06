import os
import logging
from typing import List, Optional, Dict
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QTextEdit, QComboBox, QGroupBox,
    QFileDialog, QMessageBox, QFrame, QLineEdit,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QCheckBox,
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

            employees = self.validation_service.search_employees_for_manual_match(
                query, sheet_name=current_sheet, limit=100
            )

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
        self.match_list.currentItemChanged.connect(self.on_match_selection_changed)
        match_layout.addWidget(self.match_list)

        self.no_match_label = QLabel("No possible matches found in this sheet.")
        self.no_match_label.setStyleSheet("color: #999; padding: 8px;")
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

        if result.status == OCRStatus.UNMATCHED:
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
                    text = f"{emp.employee_id} - {emp.name} ({emp.rank})  [{score:.0f}% match]"
                    item = QListWidgetItem(text)
                    item.setData(Qt.UserRole, emp)
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


class VerificationSummaryDialog(QDialog):
    def __init__(self, workbook_name: str, sheet_name: str, images_count: int,
                 total: int, confirmed: int, corrected: int, skipped: int,
                 shift: str, rows_to_mark: int,
                 ready_results: List = None, parent=None):
        super().__init__(parent)
        self.rows_to_mark = rows_to_mark
        self.ready_results = ready_results or []
        self.setup_ui(workbook_name, sheet_name, images_count, total, confirmed, corrected, skipped, shift)

    def setup_ui(self, workbook_name, sheet_name, images_count, total, confirmed, corrected, skipped, shift):
        self.setWindowTitle("Verification Summary")
        self.setModal(True)
        self.resize(520, 500)

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
            f"Shift:  {shift}",
            f"Rows To Mark:  {self.rows_to_mark}",
        ]

        for line in lines:
            if line == "":
                layout.addSpacing(4)
            else:
                label = QLabel(line)
                if line.startswith("Rows To Mark") or line.startswith("Shift"):
                    label.setFont(QFont("", 11, QFont.Bold))
                layout.addWidget(label)

        layout.addSpacing(8)

        # Employee list header
        emp_header = QLabel("Employees to be written:")
        emp_header.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(emp_header)

        # Scrollable employee list
        self.emp_list = QListWidget()
        self.emp_list.setMaximumHeight(180)
        for result in self.ready_results:
            emp = result.matched_employee
            if emp:
                corrected_mark = " [CORRECTED]" if result.manually_corrected else ""
                item_text = f"{emp.employee_id}  —  {emp.name}{corrected_mark}"
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
    def __init__(self, written: int, overwrites: int, skipped: int, errors: int, parent=None):
        super().__init__(parent)
        self.setup_ui(written, overwrites, skipped, errors)

    def setup_ui(self, written, overwrites, skipped, errors):
        self.setWindowTitle("Commit Results")
        self.setModal(True)
        self.resize(400, 280)

        layout = QVBoxLayout()

        lines = [
            ("Records Written:", str(written), False),
            ("Overwrites:", str(overwrites), False),
            ("Skipped:", str(skipped), False),
            ("Errors:", str(errors), errors > 0),
        ]

        header = QLabel("Workbook Saved Successfully" if errors == 0 else "Commit Completed with Errors")
        header.setFont(QFont("", 14, QFont.Bold))
        header.setStyleSheet("color: #4CAF50;" if errors == 0 else "color: #FF9800;")
        layout.addWidget(header)
        layout.addSpacing(12)

        for label_text, value, is_error in lines:
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            val = QLabel(value)
            val.setFont(QFont("", 12, QFont.Bold))
            if is_error:
                val.setStyleSheet("color: red;")
            else:
                val.setStyleSheet("color: #333;")
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)

        layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("padding: 8px 32px;")
        layout.addWidget(ok_btn, alignment=Qt.AlignCenter)

        self.setLayout(layout)


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
        self.date_combo = QComboBox()
        self.date_combo.addItems([str(d) for d in range(1, 32)])
        from datetime import datetime
        current_day = datetime.now().day
        if current_day <= 31:
            self.date_combo.setCurrentText(str(current_day))
        else:
            self.date_combo.setCurrentText("15")
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

        # Check if selected model supports vision
        idx = self.model_combo.currentIndex()
        if idx >= 0:
            supports_vision = self.model_combo.itemData(idx, Qt.UserRole + 1)
            if not supports_vision:
                model_name = self.model_combo.currentText()
                QMessageBox.warning(
                    self, "Model Not Compatible",
                    f"The selected model does not support image processing.\n\n"
                    f"Current model: {model_name}\n\n"
                    f"Please select a vision-capable model from the dropdown "
                    f"(models labeled 'Vision') before processing images."
                )
                return

        self.validation_results.clear()
        self.raw_response_text.clear()

        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.progress_bar.setValue(0)

        self.process_button.setEnabled(False)
        self.browse_button.setEnabled(False)

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

        self.verify_button.setEnabled(True)
        self.verify_status_label.setText(f"{len(validation_results)} records extracted. Click to review.")

    def handle_ocr_error(self, error_message: str):
        QMessageBox.critical(self, "OCR Processing Error",
                           f"OCR processing failed:\n{error_message}")

        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        self.process_button.setEnabled(True)
        self.browse_button.setEnabled(True)

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

        self._perform_commit(ready_results, day, shift)

    def _perform_commit(self, ready_results: List[OCRValidationResult], day: int, shift: str):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Writing to workbook...")

        self.save_button.setEnabled(False)
        self.verify_button.setEnabled(False)

        total = len(ready_results)
        success_count = 0
        overwrite_count = 0
        error_count = 0

        active_sheet = self.main_window.active_sheet_name if self.main_window else None

        for i, result in enumerate(ready_results):
            try:
                old_value = self.attendance_service.mark(
                    result.matched_employee,
                    day,
                    shift,
                    active_sheet
                )

                if old_value is not None and old_value != "":
                    overwrite_count += 1

                success_count += 1

                self.progress_bar.setValue(int((i + 1) / total * 100))
                self.status_label.setText(f"Writing record {i + 1}/{total}...")

            except Exception as e:
                error_count += 1
                logging.error(f"Failed to commit {result.ocr_id}: {e}")

        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        self.save_button.setEnabled(True)
        self.verify_button.setEnabled(True)

        # Auto-save workbook after commit
        try:
            if self.main_window:
                self.attendance_service.save(self.main_window.workbook_path)
                logging.info(f"OCR COMMIT: Workbook saved to {self.main_window.workbook_path}")
        except Exception as e:
            logging.error(f"OCR COMMIT: Failed to save workbook: {e}")
            QMessageBox.warning(self, "Save Warning",
                              f"Records were written but workbook could not be auto-saved: {e}")

        skipped = sum(1 for r in self.validation_results if not r.is_checked)

        dialog = PostCommitSummaryDialog(
            written=success_count,
            overwrites=overwrite_count,
            skipped=skipped,
            errors=error_count,
            parent=self
        )
        dialog.exec()

        self.validation_results = [r for r in self.validation_results if r not in ready_results]
        self.update_statistics()
        self.update_commit_readiness()

    def refresh_sheet(self):
        if self.validation_results or self.current_images:
            reply = QMessageBox.question(
                self,
                "Sheet Changed",
                "The active sheet has changed. This will clear current OCR results. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
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

            active_sheet = self.main_window.active_sheet_name if self.main_window else "(none)"
            self.active_sheet_label.setText(f"Active Sheet: {active_sheet}")

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
