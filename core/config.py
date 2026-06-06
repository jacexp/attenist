"""
Configuration Management
Handles config.json for persistent settings (API keys, etc.)
"""
import json
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any


class ConfigManager:
    """Manages application configuration stored in config.json."""

    DEFAULT_CONFIG = {
        "gemini_api_key": "",
        "gemini_provider": "google",
        "gemini_base_url": "",
        "gemini_model": "gemini-2.5-flash",
        "app_version": "2.0.0"
    }
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load config from file, create default if missing."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Merge with defaults for any missing keys
                merged = self.DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to load config.json: {e}. Using defaults.")
                return self.DEFAULT_CONFIG.copy()
        else:
            # Create default config file
            self._save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save config to file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            logging.error(f"Failed to save config.json: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save."""
        self._config[key] = value
        self._save_config(self._config)
    
    def get_gemini_api_key(self) -> str:
        """Get the stored Gemini API key."""
        return self.get("gemini_api_key", "")
    
    def set_gemini_api_key(self, api_key: str) -> None:
        """Store the Gemini API key."""
        self.set("gemini_api_key", api_key.strip())
    
    def has_valid_api_key(self) -> bool:
        """Check if a valid API key is configured."""
        key = self.get_gemini_api_key()
        return bool(key and key.strip())
    
    def get_gemini_provider(self) -> str:
        return self.get("gemini_provider", "google")
    
    def set_gemini_provider(self, provider: str) -> None:
        self.set("gemini_provider", provider)
    
    def get_gemini_base_url(self) -> str:
        return self.get("gemini_base_url", "")
    
    def set_gemini_base_url(self, url: str) -> None:
        self.set("gemini_base_url", url)
    
    def get_gemini_model(self) -> str:
        return self.get("gemini_model", "gemini-flash-latest")
    
    def set_gemini_model(self, model: str) -> None:
        self.set("gemini_model", model)

    def get_verification_auto_advance(self) -> bool:
        """Get auto-advance setting for verification wizard (default: True)."""
        return self._config.get("verification_auto_advance", True)

    def set_verification_auto_advance(self, enabled: bool) -> None:
        """Set auto-advance setting for verification wizard."""
        self._config["verification_auto_advance"] = enabled
        self._save_config(self._config)


# Global config instance
config = ConfigManager()
