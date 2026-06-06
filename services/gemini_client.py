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
    
    @staticmethod
    def normalize_model_name(model_name: str) -> str:
        """
        Normalize model name for API calls.
        
        The models.list() API returns names like 'models/gemini-2.5-flash'
        but generate_content() expects just 'gemini-2.5-flash'.
        """
        if not model_name:
            return model_name
            
        # Remove 'models/' prefix if present
        if model_name.startswith('models/'):
            normalized = model_name[7:]  # Remove 'models/' prefix
        else:
            normalized = model_name
            
        return normalized
    
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
        self.raw_model_name = model or config.get_gemini_model() or settings.get_model_name()
        self.model_name = self.normalize_model_name(self.raw_model_name)
        
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
            logging.info(f"Raw Model: {self.raw_model_name}")
            logging.info(f"Normalized Model: {self.model_name}")
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
            logging.info(f"MODEL_FORMAT_DEBUG: Making API call")
            logging.info(f"  Raw model name (from config): '{self.raw_model_name}'")
            logging.info(f"  Normalized model name (for API): '{self.model_name}'")
            logging.info(f"  Images count: {len(images) if images else 0}")
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=content
            )
            
            if not response.text:
                raise RuntimeError("Provider returned an empty response.")
                
            logging.info(f"MODEL_FORMAT_DEBUG: API call successful")
            logging.info(f"  Response length: {len(response.text)} chars")
            return response.text
            
        except Exception as e:
            logging.error(f"MODEL_FORMAT_DEBUG: API call failed")
            logging.error(f"  Raw model name: '{self.raw_model_name}'")
            logging.error(f"  Normalized model name: '{self.model_name}'")
            logging.error(f"  Error: {e}")
            
            # Provide enhanced error message for model format issues
            if "INVALID_ARGUMENT" in str(e) and "model" in str(e).lower():
                enhanced_msg = (
                    f"Selected model is using an invalid API identifier.\n\n"
                    f"Raw Model: {self.raw_model_name}\n"
                    f"Normalized Model: {self.model_name}\n"
                    f"Provider Error: {e}\n\n"
                    f"This may indicate a model name format issue. "
                    f"Check that the model name is compatible with your provider."
                )
                raise RuntimeError(enhanced_msg)
            else:
                raise RuntimeError(f"Provider API error: {e}")
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models from the provider with metadata."""
        try:
            models = self.client.models.list()
            all_models = []
            
            for m in models:
                # Extract model capabilities
                capabilities = getattr(m, 'capabilities', {})
                generation_methods = getattr(m, 'supported_generation_methods', [])
                
                # Determine if model supports vision
                supports_vision = (
                    'vision' in str(generation_methods).lower() or
                    'image' in str(capabilities).lower() or
                    'multimodal' in str(capabilities).lower()
                )
                
                # Create model metadata entry
                model_info = {
                    'name': m.name,
                    'description': getattr(m, 'description', ''),
                    'display_name': getattr(m, 'display_name', m.name),
                    'supports_vision': supports_vision,
                    'capabilities': capabilities,
                    'generation_methods': generation_methods
                }
                all_models.append(model_info)
                
                # Log detailed model information for debugging
                logging.info(f"MODEL_FORMAT_DEBUG: discovered model")
                logging.info(f"  Raw name from API: '{m.name}'")
                logging.info(f"  Display name: '{getattr(m, 'display_name', m.name)}'")
                logging.info(f"  Supports vision: {supports_vision}")
                    
            logging.info(f"MODEL_DISCOVERY: Provider returned {len(all_models)} total models")
            for model in all_models:
                vision_label = "(Vision)" if model['supports_vision'] else "(Text Only)"
                logging.info(f"MODEL_DISCOVERY: {model['name']} {vision_label}")
                    
            return all_models
        except Exception as e:
            logging.warning(f"MODEL_DISCOVERY: Failed to list models from provider: {e}")
            return []
