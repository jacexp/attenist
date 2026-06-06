"""
Application Settings
Centralized configuration for the Attenist application.
"""
import os

class Settings:
    """Application settings management."""
    
    # Gemini API Configuration
    GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY', '')
    
    # Provider Configuration
    # Set to 'google' for Google's public endpoint, or custom provider name
    GEMINI_PROVIDER = os.getenv('GEMINI_PROVIDER', 'google')
    
    # Custom endpoint/base URL for provider/gateway (e.g., OpenRouter, LiteLLM, custom proxy)
    # Examples:
    #   OpenRouter: https://openrouter.ai/api/v1
    #   LiteLLM: http://localhost:4000
    #   Custom: https://your-gateway.com/v1
    GEMINI_BASE_URL = os.getenv('GEMINI_BASE_URL', '')
    
    # Model Configuration
    # Provider-specific model names. Examples:
    #   Google: gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash
    #   OpenRouter: google/gemini-flash-1.5, google/gemini-pro-1.5
    #   Custom: gemini-flash-latest, gemini-3-flash-preview
    DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
    CURRENT_GEMINI_MODEL = os.getenv('GEMINI_MODEL', DEFAULT_GEMINI_MODEL)
    
    # Application Paths
    DB_PATH = "employees.db"
    LOG_FILE = "attenist.log"
    
    @classmethod
    def get_model_name(cls) -> str:
        """Returns the configured Gemini model name."""
        return cls.CURRENT_GEMINI_MODEL
    
    @classmethod
    def get_base_url(cls) -> str:
        """Returns the configured base URL (empty for default Google endpoint)."""
        return cls.GEMINI_BASE_URL
    
    @classmethod
    def get_provider(cls) -> str:
        """Returns the configured provider name."""
        return cls.GEMINI_PROVIDER

settings = Settings()
