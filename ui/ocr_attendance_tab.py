"""
OCR Attendance Tab UI
Comprehensive UI for OCR attendance workflow with verification table and batch processing.
"""
import os
import logging
from typing import List, Optional, Dict
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QTextEdit, QComboBox, QCheckBox, QGroupBox,
    QFileDialog, QMessageBox, QSplitter, QFrame, QLineEdit,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QPixmap

from services.ocr.ocr_service import OCRService, OCRServiceException
from services.ocr.validation_service import OCRValidationService, OCRValidationResult, OCRStatus
from database.database_service import DatabaseService
from core.models import Employee
from services.attendance_service import AttendanceService
from core.config import config
from ui.api_key_dialog import FirstLaunchManager


class OCRProcessingThread(QThread):
    """Thread for handling OCR processing without blocking UI."""
    
    progress_updated = Signal(int, str)  # progress percentage, status message
    ocr_completed = Signal(list, list)   # validation_results, raw_responses
    error_occurred = Signal(str)         # error message
    
    def __init__(self, image_paths: List[str], ocr_service: OCRService, 
                 validation_service: OCRValidationService):
        super().__init__()
        self.image_paths = image_paths
        self.ocr_service = ocr_service
        self.validation_service = validation_service
    
    def run(self):
        """Run OCR processing in background thread."""
        try:
            total_images = len(self.image_paths)
            
            # Step 1: OCR Extraction
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
            
            # Step 2: Validation and Matching
            self.progress_updated.emit(60, "Validating and matching employees...")
            
            validation_results = self.validation_service.validate_ocr_results(all_extracted_data)
            
            self.progress_updated.emit(100, "OCR processing completed!")
            self.ocr_completed.emit(validation_results, all_raw_responses)
            
        except Exception as e:
            logging.error(f"OCR processing thread failed: {e}")
            self.error_occurred.emit(str(e))


class EmployeeSearchDialog(QDialog):
    """Dialog for searching and selecting employees during manual correction."""
    
    def __init__(self, validation_service: OCRValidationService, parent=None):
        super().__init__(parent)
        self.validation_service = validation_service
        self.selected_employee = None
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Search Employee")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout()
        
        # Search input
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter employee ID or name...")
        self.search_input.textChanged.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.select_employee)
        layout.addWidget(self.results_list)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.select_employee)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def perform_search(self, query: str):
        """Perform employee search and update results."""
        self.results_list.clear()
        
        if len(query) < 2:
            return
        
        try:
            employees = self.validation_service.search_employees_for_manual_match(query, 20)
            
            for emp in employees:
                item_text = f"{emp.employee_id} - {emp.name} ({emp.rank}) [{emp.sheet_name}]"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, emp)
                self.results_list.addItem(item)
                
        except Exception as e:
            logging.error(f"Employee search failed: {e}")
    
    def select_employee(self):
        """Select the highlighted employee and close dialog."""
        current_item = self.results_list.currentItem()
        if current_item:
            self.selected_employee = current_item.data(Qt.UserRole)
            self.accept()
        else:
            QMessageBox.warning(self, "No Selection", "Please select an employee from the list.")


class OCRAttendanceTab(QWidget):
    """Main OCR Attendance tab widget."""
    
    def __init__(self, database_service: DatabaseService, attendance_service: AttendanceService):
        super().__init__()
        self.database_service = database_service
        self.attendance_service = attendance_service
        
        # Initialize services
        self.ocr_service = None
        self.validation_service = OCRValidationService(database_service)
        
        # Data
        self.validation_results: List[OCRValidationResult] = []
        self.current_images: List[str] = []
        self.ocr_enabled = False
        
        # UI setup
        self.setup_ui()
        self.setup_connections()
        
        # Initialize OCR service (uses config)
        self.initialize_ocr_service()
    
    def setup_ui(self):
        """Setup the complete UI layout."""
        main_layout = QVBoxLayout()
        
        # Header section
        header_group = QGroupBox("OCR Attendance Processing")
        header_layout = QVBoxLayout()
        
        # Status and statistics
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Ready to process images")
        self.stats_label.setFont(QFont("", 10, QFont.Bold))
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        
        # API status
        self.api_status_label = QLabel("Gemini API: Not initialized")
        stats_layout.addWidget(self.api_status_label)
        header_layout.addLayout(stats_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        header_layout.addWidget(self.progress_bar)
        
        # Status message
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        header_layout.addWidget(self.status_label)
        
        header_group.setLayout(header_layout)
        main_layout.addWidget(header_group)
        
        # Upload section
        upload_group = QGroupBox("Image Upload")
        upload_layout = QHBoxLayout()
        
        self.browse_button = QPushButton("Browse Images...")
        self.browse_button.clicked.connect(self.browse_images)
        upload_layout.addWidget(self.browse_button)
        
        self.process_button = QPushButton("Process Images")
        self.process_button.clicked.connect(self.process_images)
        self.process_button.setEnabled(False)
        upload_layout.addWidget(self.process_button)
        
        upload_layout.addStretch()
        
        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_all)
        upload_layout.addWidget(self.clear_button)
        
        upload_group.setLayout(upload_layout)
        main_layout.addWidget(upload_group)
        
        # Selected files display
        self.files_label = QLabel("No images selected")
        main_layout.addWidget(self.files_label)
        
        # Batch info section (Date + Shift selectors)
        batch_group = QGroupBox("Batch Info")
        batch_layout = QHBoxLayout()
        
        batch_layout.addWidget(QLabel("Date:"))
        self.date_combo = QComboBox()
        # Days 1-31
        self.date_combo.addItems([str(d) for d in range(1, 32)])
        # Default to current day or 15
        from datetime import datetime
        current_day = datetime.now().day
        if current_day <= 31:
            self.date_combo.setCurrentText(str(current_day))
        else:
            self.date_combo.setCurrentText("15")
        batch_layout.addWidget(self.date_combo)
        
        batch_layout.addWidget(QLabel("Shift:"))
        self.batch_shift_combo = QComboBox()
        self.batch_shift_combo.addItems(["", "A", "B", "C", "G", "WO", "AB"])
        self.batch_shift_combo.setCurrentText("A")
        self.batch_shift_combo.setMinimumWidth(100)
        batch_layout.addWidget(self.batch_shift_combo)
        
        batch_layout.addStretch()
        
        # Summary label
        self.batch_summary_label = QLabel("Shift: A | Rows: 0")
        self.batch_summary_label.setStyleSheet("font-weight: bold; color: #333; padding: 5px;")
        batch_layout.addWidget(self.batch_summary_label)
        
        batch_group.setLayout(batch_layout)
        main_layout.addWidget(batch_group)
        
        # Upload section
        upload_group = QGroupBox("Image Upload")
        upload_layout = QHBoxLayout()
        
        self.browse_button = QPushButton("Browse Images...")
        self.browse_button.clicked.connect(self.browse_images)
        upload_layout.addWidget(self.browse_button)
        
        self.process_button = QPushButton("Process Images")
        self.process_button.clicked.connect(self.process_images)
        self.process_button.setEnabled(False)
        upload_layout.addWidget(self.process_button)
        
        upload_layout.addStretch()
        
        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_all)
        upload_layout.addWidget(self.clear_button)
        
        upload_group.setLayout(upload_layout)
        main_layout.addWidget(upload_group)
        
        # Selected files display
        self.files_label = QLabel("No images selected")
        main_layout.addWidget(self.files_label)
        
        # Main content splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Verification table
        self.setup_verification_table()
        splitter.addWidget(self.verification_table)
        
        # Debug/raw response area
        debug_group = QGroupBox("Debug Information")
        debug_layout = QVBoxLayout()
        
        self.raw_response_text = QTextEdit()
        self.raw_response_text.setMaximumHeight(150)
        self.raw_response_text.setReadOnly(True)
        debug_layout.addWidget(self.raw_response_text)
        
        debug_group.setLayout(debug_layout)
        splitter.addWidget(debug_group)
        
        splitter.setSizes([400, 150])
        main_layout.addWidget(splitter)
        
        # Commit section
        commit_group = QGroupBox("Batch Commit")
        commit_layout = QHBoxLayout()
        
        self.commit_stats_label = QLabel("No rows ready for commit")
        commit_layout.addWidget(self.commit_stats_label)
        commit_layout.addStretch()
        
        self.commit_button = QPushButton("Commit to Excel")
        self.commit_button.clicked.connect(self.commit_to_excel)
        self.commit_button.setEnabled(False)
        self.commit_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        commit_layout.addWidget(self.commit_button)
        
        commit_group.setLayout(commit_layout)
        main_layout.addWidget(commit_group)
        
        self.setLayout(main_layout)
    
    def setup_verification_table(self):
        """Setup the verification table with all required columns (no per-row shift)."""
        self.verification_table = QTableWidget()
        
        # Column setup: [✓], Status, OCR ID, OCR Name, Matched Employee, Notes, Actions
        column_headers = ["✓", "Status", "OCR ID", "OCR Name", "Matched Employee", "Notes", "Actions"]
        self.verification_table.setColumnCount(len(column_headers))
        self.verification_table.setHorizontalHeaderLabels(column_headers)
        
        # Configure table
        header = self.verification_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # OCR ID
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # OCR Name
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # Matched Employee
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # Notes
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Actions
        
        self.verification_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verification_table.setAlternatingRowColors(True)
    
    def setup_connections(self):
        """Setup signal connections."""
        # Timer for updating commit stats
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_commit_stats)
        self.update_timer.start(1000)  # Update every second
    
    def initialize_ocr_service(self):
        """Initialize the OCR service using config.json."""
        # Startup diagnostics
        has_key = config.has_valid_api_key()
        logging.info(f"=== OCR Startup Diagnostics ===")
        logging.info(f"Config file found: True")
        logging.info(f"API key configured: {config.has_valid_api_key()}")
        logging.info(f"OCR enabled: {config.has_valid_api_key()}")
        logging.info(f"==================================")
        
        if config.has_valid_api_key():
            try:
                self.ocr_service = OCRService(config.get_gemini_api_key())
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
            # No API key configured - show disabled state with configure button
            self.ocr_enabled = False
            self.api_status_label.setText("Gemini API: Not Configured")
            self.api_status_label.setStyleSheet("color: orange;")
            self._enable_ocr_controls(False)
            self._add_configure_button()
            logging.info("OCR disabled: No API key configured")
    
    def _enable_ocr_controls(self, enabled: bool):
        """Enable or disable OCR-related controls."""
        self.ocr_enabled = enabled
        self.process_button.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        if hasattr(self, 'configure_btn') and self.configure_btn:
            self.configure_btn.setVisible(not enabled)
    
    def _add_configure_button(self):
        """Add a 'Configure API Key' button to the header."""
        if hasattr(self, 'configure_btn') and self.configure_btn:
            return  # Already added
        
        self.configure_btn = QPushButton("Configure Gemini API Key")
        self.configure_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 8px 16px;")
        self.configure_btn.clicked.connect(self._configure_api_key)
        
        # Add to header group's stats layout
        for child in self.children():
            if isinstance(child, QGroupBox) and child.title() == "OCR Attendance Processing":
                layout = child.layout()
                if layout and layout.count() > 0:
                    stats_layout = layout.itemAt(0).layout() if layout.itemAt(0) else None
                    if stats_layout:
                        stats_layout.addWidget(self.configure_btn)
                        break
    
    def _configure_api_key(self):
        """Open API key configuration dialog."""
        from ui.api_key_dialog import FirstLaunchManager
        manager = FirstLaunchManager(self)
        if manager.show_reconfigure_dialog():
            # Key was saved, reinitialize
            self.initialize_ocr_service()
    
    def browse_images(self):
        """Open file dialog to select images."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Attendance Images",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
        )
        
        if file_paths:
            self.current_images = file_paths
            self.update_files_display()
            self.process_button.setEnabled(True)
    
    def update_files_display(self):
        """Update the display of selected files."""
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
        """Start OCR processing of selected images."""
        if not self.current_images:
            QMessageBox.warning(self, "No Images", "Please select images to process.")
            return
        
        if not self.ocr_enabled or not self.ocr_service:
            QMessageBox.warning(self, "OCR Not Configured", 
                              "Please configure your Gemini API key first using the 'Configure Gemini API Key' button.")
            return
        
        # Clear previous results
        self.validation_results.clear()
        self.verification_table.setRowCount(0)
        self.raw_response_text.clear()
        
        # Show progress UI
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Disable UI during processing
        self.process_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        
        # Start OCR processing thread
        self.ocr_thread = OCRProcessingThread(
            self.current_images, 
            self.ocr_service, 
            self.validation_service
        )
        self.ocr_thread.progress_updated.connect(self.update_progress)
        self.ocr_thread.ocr_completed.connect(self.handle_ocr_completed)
        self.ocr_thread.error_occurred.connect(self.handle_ocr_error)
        self.ocr_thread.start()
    
    def update_progress(self, percentage: int, message: str):
        """Update progress bar and status message."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)
    
    def handle_ocr_completed(self, validation_results: List[OCRValidationResult], 
                           raw_responses: List[str]):
        """Handle completed OCR processing."""
        self.validation_results = validation_results
        
        # Update UI
        self.populate_verification_table()
        self.update_statistics()
        
        # Show raw responses in debug area
        self.raw_response_text.setText("\n\n".join(raw_responses))
        
        # Hide progress UI
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        
        # Re-enable UI
        self.process_button.setEnabled(True)
        self.browse_button.setEnabled(True)
    
    def handle_ocr_error(self, error_message: str):
        """Handle OCR processing error."""
        QMessageBox.critical(self, "OCR Processing Error", 
                           f"OCR processing failed:\n{error_message}")
        
        # Hide progress UI
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        
        # Re-enable UI
        self.process_button.setEnabled(True)
        self.browse_button.setEnabled(True)
    
    def populate_verification_table(self):
        """Populate verification table with validation results (no per-row shift)."""
        self.verification_table.setRowCount(len(self.validation_results))
        
        for row, result in enumerate(self.validation_results):
            # Column 0: Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(result.is_checked)
            checkbox.setEnabled(result.checkbox_enabled)
            checkbox.stateChanged.connect(lambda state, r=result: setattr(r, 'is_checked', bool(state)))
            self.verification_table.setCellWidget(row, 0, checkbox)
            
            # Column 1: Status with color coding
            status_item = QTableWidgetItem(result.status.value)
            if result.status == OCRStatus.CONFIRMED:
                status_item.setBackground(QColor(200, 255, 200))  # Light green
            elif result.status == OCRStatus.UNMATCHED:
                status_item.setBackground(QColor(255, 255, 200))  # Light yellow
            elif result.status == OCRStatus.INVALID:
                status_item.setBackground(QColor(255, 200, 200))  # Light red
            elif result.status == OCRStatus.REVIEW:
                status_item.setBackground(QColor(255, 220, 150))  # Light orange
            self.verification_table.setItem(row, 1, status_item)
            
            # Column 2: OCR ID
            self.verification_table.setItem(row, 2, QTableWidgetItem(result.ocr_id))
            
            # Column 3: OCR Name
            self.verification_table.setItem(row, 3, QTableWidgetItem(result.ocr_name))
            
            # Column 4: Matched Employee
            if result.matched_employee:
                emp_text = f"{result.matched_employee.employee_id} - {result.matched_employee.name}"
                if result.matched_employee.rank:
                    emp_text += f" ({result.matched_employee.rank})"
            else:
                emp_text = "No match"
            self.verification_table.setItem(row, 4, QTableWidgetItem(emp_text))
            
            # Column 5: Notes
            self.verification_table.setItem(row, 5, QTableWidgetItem(result.validation_notes))
            
            # Column 6: Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            
            if result.status in [OCRStatus.UNMATCHED, OCRStatus.INVALID, OCRStatus.REVIEW]:
                correct_button = QPushButton("Correct")
                correct_button.clicked.connect(lambda _, r=result, row_idx=row: self.correct_entry(r, row_idx))
                actions_layout.addWidget(correct_button)
            
            self.verification_table.setCellWidget(row, 6, actions_widget)
    
    def correct_entry(self, result: OCRValidationResult, row_index: int):
        """Open correction dialog for a validation result."""
        dialog = EmployeeSearchDialog(self.validation_service, self)
        
        if dialog.exec() == QDialog.Accepted and dialog.selected_employee:
            # Apply manual correction
            corrected_result = self.validation_service.manual_correction(
                result, selected_employee=dialog.selected_employee
            )
            
            # Update the result in our list
            self.validation_results[row_index] = corrected_result
            
            # Refresh the table row
            self.populate_verification_table()
            
            QMessageBox.information(self, "Correction Applied", 
                                  f"Employee {dialog.selected_employee.employee_id} "
                                  f"has been matched to OCR entry {result.ocr_id}")
    
    def update_statistics(self):
        """Update statistics display."""
        if not self.validation_results:
            self.stats_label.setText("No results to display")
            return
        
        stats = self.validation_service.get_validation_statistics()
        
        self.stats_label.setText(
            f"Total: {stats['total_processed']} | "
            f"Confirmed: {stats['confirmed']} | "
            f"Unmatched: {stats['unmatched']} | "
            f"Invalid: {stats['invalid']} | "
            f"Review: {stats['review']}"
        )
    
    def update_commit_stats(self):
        """Update commit statistics and button state."""
        if not self.validation_results:
            self.commit_stats_label.setText("No rows ready for commit")
            self.commit_button.setEnabled(False)
            self.update_batch_summary()
            return
        
        # Check global shift
        global_shift = self.batch_shift_combo.currentText()
        has_global_shift = bool(global_shift)
        
        if not has_global_shift:
            self.commit_stats_label.setText("Select a shift to enable commit")
            self.commit_button.setEnabled(False)
            self.update_batch_summary()
            return
        
        ready_results = self.validation_service.filter_ready_for_commit(self.validation_results)
        ready_count = len(ready_results)
        total_checked = sum(1 for r in self.validation_results if r.is_checked)
        
        self.commit_stats_label.setText(
            f"Ready for commit: {ready_count}/{total_checked} checked rows"
        )
        
        self.commit_button.setEnabled(ready_count > 0)
        self.update_batch_summary()
    
    def update_batch_summary(self):
        """Update the batch summary label with shift and row count."""
        global_shift = self.batch_shift_combo.currentText()
        if not self.validation_results:
            self.batch_summary_label.setText(f"Shift: {global_shift or 'Not Selected'} | Rows: 0")
            return
        
        total_checked = sum(1 for r in self.validation_results if r.is_checked)
        ready_results = self.validation_service.filter_ready_for_commit(self.validation_results)
        ready_count = len(ready_results)
        
        self.batch_summary_label.setText(
            f"Shift: {global_shift or 'Not Selected'} | "
            f"Checked: {total_checked} | Ready: {ready_count}"
        )
    
    def commit_to_excel(self):
        """Commit validated results to Excel."""
        ready_results, warnings = self.validation_service.validate_commit_readiness(
            self.validation_results
        )
        
        if not ready_results:
            QMessageBox.warning(self, "Nothing to Commit", 
                              "No rows are ready for commit.\n\n" +
                              "\n".join(warnings) if warnings else "")
            return
        
        # Validate global shift
        global_shift = self.batch_shift_combo.currentText()
        if not global_shift:
            QMessageBox.warning(self, "No Shift Selected", 
                              "Please select a shift for this batch before committing.")
            return
        
        # Get selected day
        day = int(self.date_combo.currentText())
        
        # Show confirmation dialog
        message = f"Ready to commit {len(ready_results)} attendance entries to Excel.\n\n"
        message += f"Date: {day} | Shift: {global_shift}\n\n"
        if warnings:
            message += "Warnings:\n" + "\n".join(warnings[:5])  # Show first 5 warnings
            if len(warnings) > 5:
                message += f"\n... and {len(warnings) - 5} more warnings"
            message += "\n\n"
        
        message += "Continue with commit?"
        
        reply = QMessageBox.question(self, "Confirm Commit", message,
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        # Perform commit with global shift and day
        self.perform_batch_commit(ready_results, day, global_shift)
    
    def perform_batch_commit(self, ready_results: List[OCRValidationResult], day: int, shift: str):
        """Perform the actual batch commit to Excel using global shift."""
        success_count = 0
        error_count = 0
        error_messages = []
        
        for result in ready_results:
            try:
                # Use existing attendance service to write to Excel
                old_value = self.attendance_service.mark(
                    result.matched_employee,
                    day,
                    shift
                )
                
                success_count += 1
                logging.info(f"OCR COMMIT: {result.matched_employee.employee_id} "
                           f"({result.matched_employee.name}) marked {shift} "
                           f"(was: {old_value})")
                
            except Exception as e:
                error_count += 1
                error_msg = f"Failed to commit {result.ocr_id}: {e}"
                error_messages.append(error_msg)
                logging.error(error_msg)
        
        # Show results
        if error_count == 0:
            QMessageBox.information(self, "Commit Successful", 
                                  f"Successfully committed {success_count} attendance entries!")
        else:
            error_detail = "\n".join(error_messages[:5])  # Show first 5 errors
            if len(error_messages) > 5:
                error_detail += f"\n... and {len(error_messages) - 5} more errors"
            
            QMessageBox.warning(self, "Commit Completed with Errors",
                              f"Committed: {success_count}\nErrors: {error_count}\n\n"
                              f"Error details:\n{error_detail}")
        
        # Clear committed results
        self.validation_results = [r for r in self.validation_results if r not in ready_results]
        self.populate_verification_table()
        self.update_statistics()
    
    def clear_all(self):
        """Clear all data and reset the tab."""
        reply = QMessageBox.question(self, "Clear All Data", 
                                   "This will clear all OCR results and selected images. Continue?",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.validation_results.clear()
            self.current_images.clear()
            self.verification_table.setRowCount(0)
            self.raw_response_text.clear()
            self.update_files_display()
            self.update_statistics()
            self.process_button.setEnabled(False)