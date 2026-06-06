import logging
import os
import sys

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from ui.main_window import MainWindow
from ui.splash_dialog import SplashDialog

from workbook.loader import WorkbookLoader
from workbook.indexes.employee import EmployeeIndexer
from workbook.indexes.date import DateIndexer

from core.config import config

logging.basicConfig(
    filename="attenist.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def main():
    app = QApplication(sys.argv)

    # Workbook Selection (before splash — user-interactive)
    file_path, _ = QFileDialog.getOpenFileName(
        None,
        "Open Attendance Workbook",
        "",
        "Excel Files (*.xlsx)"
    )

    if not file_path:
        return

    # Show splash screen
    splash = SplashDialog()
    splash.show()
    QApplication.processEvents()

    try:
        # Stage 1: Load configuration
        splash.update(10, "Loading configuration...")

        # Stage 2: Load workbook
        splash.update(20, "Opening workbook...")
        splash.set_workbook_name(os.path.basename(file_path))
        QApplication.processEvents()

        try:
            workbook = WorkbookLoader().load(file_path)
        except PermissionError:
            splash.close()
            QMessageBox.critical(
                None,
                "File Locked",
                f"Cannot open '{os.path.basename(file_path)}'.\n\n"
                "Please close it in Excel and try again."
            )
            return

        # Stage 3: Build employee index
        splash.update(40, "Building employee index...")
        QApplication.processEvents()
        employees = EmployeeIndexer().build(workbook)

        # Stage 4: Build date index
        splash.update(55, "Building date index...")
        QApplication.processEvents()
        dates = {}
        for sheet in workbook.worksheets:
            has_employees = any(emp.sheet_name == sheet.title for emp in employees)
            if has_employees:
                dates = DateIndexer().build(sheet)
                if dates:
                    break

        if not dates:
            splash.close()
            QMessageBox.critical(
                None,
                "Error",
                "No valid attendance dates found in workbook.",
            )
            return

        # Stage 5: OCR services check
        splash.update(70, "Checking OCR services...")
        QApplication.processEvents()

        if not config.has_valid_api_key():
            splash.show_ocr_warning(
                "Gemini API key not configured — OCR features will be disabled."
            )

        # Stage 6: Build MainWindow (in-memory index, no SQLite)
        splash.update(90, "Loading UI components...")
        QApplication.processEvents()

        window = MainWindow(
            workbook=workbook,
            employees=employees,
            dates=dates,
            workbook_path=file_path,
        )

        splash.update(100, "Ready")
        splash.close()

    except Exception as e:
        logging.error(f"Startup failed: {e}", exc_info=True)
        splash.close()
        QMessageBox.critical(
            None,
            "Startup Error",
            f"Application failed to start:\n{e}",
        )
        return

    window.adjustSize()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
