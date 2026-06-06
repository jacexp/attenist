"""
Gemini Client Abstraction
Handles communication with Gemini-compatible providers (Google, OpenRouter, LiteLLM, custom gateways).
"""
import logging
from typing import List, Optional, Union, Dict, Any
from pathlib import Path
from PIL import Image
import google.genai as genai
from core.config import config
from core.settings import settings


class GeminiClient:
    """
    Abstraction layer for Gemini-compatible providers.
    Supports Google's public endpoint and custom gateways (OpenRouter, LiteLLM, custom proxies).
    """
    
    def __init__(self, api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 provider: Optional[str] = None,
                 base_url: Optional[str] = None):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: API key. Falls back to config.json then env var.
            model: Model name override. Falls back to config.json then env var.
            provider: Provider name override. Falls back to config.json then env var.
            base_url: Base URL override. Falls back to config.json then env var.
        """
        self.api_key = api_key or config.get_gemini_api_key() or settings.GEMINI_API_KEY
        if not self.api_key:
            logging.error("Gemini API Key is missing. Set in config.json or GOOGLE_API_KEY env var.")
            raise ValueError("Gemini API Key is required for OCR functionality.")
        
        self.base_url = base_url or config.get_gemini_base_url() or settings.get_base_url()
        self.provider = provider or config.get_gemini_provider() or settings.get_provider()
        self.model_name = model or config.get_gemini_model() or settings.get_model_name()
        
        try:
            # Configure client with optional custom base URL for provider/gateway
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["http_options"] = {"base_url": self.base_url}
            
            self.client = genai.Client(**client_kwargs)
            
            # Diagnostic logging
            endpoint = self.base_url if self.base_url else "https://generativelanguage.googleapis.com (Google default)"
            logging.info(f"=== Gemini Client Diagnostics ===")
            logging.info(f"Provider: {self.provider}")
            logging.info(f"Endpoint: {endpoint}")
            logging.info(f"Model: {self.model_name}")
            logging.info(f"==================================")
            
        except Exception as e:
            logging.error(f"Failed to initialize Gemini client: {e}")
            raise ConnectionError(f"Could not connect to Gemini API: {e}")
    
    def generate_content(self, prompt: str, images: Optional[List[Union[str, Image.Image]]] = None) -> str:
        """
        Generate content from a prompt and optional images.
        
        Args:
            prompt: The text prompt for the model.
            images: List of image paths or PIL Image objects.
            
        Returns:
            The raw text response from the model.
            
        Raises:
            RuntimeError: If the API call fails.
        """
        try:
            content = [prompt]
            
            if images:
                for img in images:
                    if isinstance(img, str):
                        # Load image from path
                        img_obj = Image.open(img)
                        content.append(img_obj)
                    else:
                        # Use provided PIL Image object
                        content.append(img)
            
            # Log the model being used for this request
            logging.debug(f"OCR Request -> Model: {self.model_name}, Images: {len(images) if images else 0}")
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=content
            )
            
            if not response.text:
                raise RuntimeError("Provider returned an empty response.")
                
            logging.debug(f"OCR Response <- Length: {len(response.text)} chars")
            return response.text
            
        except Exception as e:
            logging.error(f"Provider API call failed: {e}")
            raise RuntimeError(f"Provider API error: {e}")
    
    def list_models(self) -> List[str]:
        """List all available models that support vision."""
        try:
            models = self.client.models.list()
            vision_models = []
            for m in models:
                # Check if model supports images (vision)
                # In the new SDK, we can check capabilities
                if 'vision' in m.supported_generation_methods or 'image' in str(m.capabilities).lower():
                    vision_models.append(m.name)
                # Fallback for known vision models if capabilities aren't explicit
                elif 'flash' in m.name or 'pro' in m.name:
                    vision_models.append(m.name)
                    
            logging.info(f"Discovered {len(vision_models)} vision-capable models from provider")
            for model in vision_models:
                logging.info(f"  Available: {model}")
                    
            return vision_models
        except Exception as e:
            logging.warning(f"Model discovery failed (provider may not support listing): {e}")
            return []
