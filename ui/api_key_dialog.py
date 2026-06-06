"""
API Key Configuration Dialog
First-launch dialog for entering Gemini API key.
"""
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from core.config import config



class ApiKeyDialog(QDialog):
    """Dialog for entering and saving Gemini API key."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Gemini API Key")
        self.setModal(True)
        self.setFixedWidth(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Title
        title_label = QLabel("Welcome to Attenist OCR")
        title_label.setFont(QFont("", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(
            "To use the OCR Attendance feature, you need a Gemini API key.\n\n"
            "1. Get your API key from: https://aistudio.google.com/app/apikey\n"
            "2. Paste it below\n"
            "3. Click Save - you only need to do this once"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #555;")
        layout.addWidget(desc_label)
        
        # API Key input group
        key_group = QGroupBox("Gemini API Key")
        key_layout = QVBoxLayout()
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Gemini API key here...")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setMinimumHeight(35)
        key_layout.addWidget(self.api_key_input)
        
        # Show/hide checkbox
        self.show_key_cb = QCheckBox("Show key")
        self.show_key_cb.toggled.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.show_key_cb)
        
        key_group.setLayout(key_layout)
        layout.addWidget(key_group)
        
        # Provider settings (advanced)
        advanced_group = QGroupBox("Advanced (Optional)")
        advanced_layout = QVBoxLayout()
        
        # Provider
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_input = QLineEdit()
        self.provider_input.setPlaceholderText("google (default)")
        self.provider_input.setText("google")
        provider_layout.addWidget(self.provider_input)
        advanced_layout.addLayout(provider_layout)
        
        # Base URL
        base_url_layout = QHBoxLayout()
        base_url_layout.addWidget(QLabel("Base URL:"))
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://generativelanguage.googleapis.com (default)")
        base_url_layout.addWidget(self.base_url_input)
        advanced_layout.addLayout(base_url_layout)
        
        # Model
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("gemini-flash-latest")
        self.model_input.setText("gemini-flash-latest")
        model_layout.addWidget(self.model_input)
        advanced_layout.addLayout(model_layout)
        
        advanced_group.setLayout(advanced_layout)
        advanced_group.setVisible(False)  # Hidden by default
        layout.addWidget(advanced_group)
        
        # Advanced toggle
        self.advanced_cb = QCheckBox("Show advanced settings")
        self.advanced_cb.toggled.connect(advanced_group.setVisible)
        layout.addWidget(self.advanced_cb)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("Save & Enable OCR")
        self.save_btn.setDefault(True)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 20px;")
        self.save_btn.clicked.connect(self._save_key)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _toggle_key_visibility(self, checked: bool):
        """Toggle password visibility."""
        if checked:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
    
    def _save_key(self):
        """Validate and save the API key."""
        api_key = self.api_key_input.text().strip()
        
        if not api_key:
            QMessageBox.warning(self, "Missing API Key", "Please enter a Gemini API key.")
            return
        
        if len(api_key) < 10:
            QMessageBox.warning(self, "Invalid API Key", "API key appears too short. Please check and try again.")
            return
        
        # Save to config
        config.set_gemini_api_key(api_key)
        config.set_gemini_provider(self.provider_input.text().strip() or "google")
        config.set_gemini_base_url(self.base_url_input.text().strip())
        config.set_gemini_model(self.model_input.text().strip() or "gemini-flash-latest")
        
        logging.info("Gemini API key saved successfully")
        QMessageBox.information(self, "Success", "API key saved! OCR is now enabled.")
        self.accept()


class FirstLaunchManager:
    """Manages first-launch API key configuration."""
    
    def __init__(self, parent=None):
        self.parent = parent
    
    def check_and_configure(self) -> bool:
        """
        Check if API key is configured.
        Returns True if OCR should be enabled, False if key is missing.
        """
        if config.has_valid_api_key():
            return True
        
        # Show dialog
        dialog = ApiKeyDialog(self.parent)
        result = dialog.exec()
        
        if result == QDialog.Accepted and config.has_valid_api_key():
            return True
        
        return False
    
    def show_reconfigure_dialog(self) -> bool:
        """Show dialog to reconfigure API key."""
        dialog = ApiKeyDialog(self.parent)
        result = dialog.exec()
        return result == QDialog.Accepted and config.has_valid_api_key()
