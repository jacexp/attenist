"""
Startup Splash Dialog — shows progress during application initialization.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel,
    QProgressBar, QApplication,
)


class SplashDialog(QDialog):
    """Non-blocking splash screen with progress bar and status text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Starting Attenist")
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setFixedSize(480, 220)
        self.setModal(False)

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)

        # Title
        title = QLabel("Attenist v2")
        title.setFont(QFont("", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Status text
        self.status_label = QLabel("Initializing...")
        self.status_label.setFont(QFont("", 10))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #555;")
        layout.addWidget(self.status_label)

        # Workbook name (hidden until needed)
        self.workbook_label = QLabel("")
        self.workbook_label.setAlignment(Qt.AlignCenter)
        self.workbook_label.setStyleSheet("color: #888; font-size: 9pt;")
        self.workbook_label.setVisible(False)
        layout.addWidget(self.workbook_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)

        # OCR warning (hidden until needed)
        self.ocr_warning = QLabel("")
        self.ocr_warning.setAlignment(Qt.AlignCenter)
        self.ocr_warning.setStyleSheet(
            "color: #cc6600; font-size: 9pt; padding: 4px;"
        )
        self.ocr_warning.setWordWrap(True)
        self.ocr_warning.setVisible(False)
        layout.addWidget(self.ocr_warning)

        layout.addStretch()
        self.setLayout(layout)

        self._workbook_timer = None
        self._workbook_shown = False

    def update(self, percent: int, status: str):
        """Update progress bar and status text. Call processEvents to keep UI responsive."""
        self.progress_bar.setValue(percent)
        self.status_label.setText(status)
        QApplication.processEvents()

    def set_workbook_name(self, name: str):
        """Show the workbook name being loaded."""
        if not name:
            return
        self.workbook_label.setText(f"Opening: {name}")
        self.workbook_label.setVisible(True)
        QApplication.processEvents()

    def show_warning(self, message: str):
        """Show a non-blocking warning message (replaces OCR warning label)."""
        self.ocr_warning.setText(message)
        self.ocr_warning.setVisible(True)
        QApplication.processEvents()

    def show_ocr_warning(self, message: str):
        """Show a non-blocking warning about OCR initialization."""
        self.show_warning(message)

    def close(self):
        """Close the splash. Safe to call multiple times."""
        if self.isVisible():
            super().close()
