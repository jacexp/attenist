"""
Application Settings
Centralized configuration for the Attenist application.
Falls back to environment variables, then config.json defaults.
"""
import os
from core.config import config

class Settings:
    """Application settings management — env var fallback for config.json."""

    # Gemini API Key (env var fallback)
    GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY', '')

    # Application Paths
    DB_PATH = "employees.db"
    LOG_FILE = "attenist.log"

    @classmethod
    def get_model_name(cls) -> str:
        """Returns configured model: config.json → env var → default."""
        return config.get_gemini_model() or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

    @classmethod
    def get_base_url(cls) -> str:
        """Returns configured base URL: config.json → env var → empty."""
        return config.get_gemini_base_url() or os.getenv('GEMINI_BASE_URL', '')

    @classmethod
    def get_provider(cls) -> str:
        """Returns configured provider: config.json → env var → 'google'."""
        return config.get_gemini_provider() or os.getenv('GEMINI_PROVIDER', 'google')

settings = Settings()
