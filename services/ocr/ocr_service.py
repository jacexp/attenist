"""
OCR Service for Gemini Vision API Integration
Handles image upload, Gemini API calls, and JSON parsing for attendance extraction.
"""
import json
import time
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from PIL import Image
import io

from services.gemini_client import GeminiClient
from core.config import config


class OCRService:
    """Service for extracting attendance data from images using Gemini Vision."""
    
    def __init__(self, api_key: str = None, discover_models: bool = True,
                 model: Optional[str] = None,
                 provider: Optional[str] = None,
                 base_url: Optional[str] = None):
        """
        Initialize OCR Service with Gemini API.

        Args:
            api_key: API key. Falls back to config.json then env var.
            discover_models: If True, attempt to discover available models.
            model: Model name override. Falls back to config.json then env var.
            provider: Provider name override. Falls back to config.json then env var.
            base_url: Base URL override. Falls back to config.json then env var.
        """
        self.gemini_client = GeminiClient(api_key, model=model, provider=provider, base_url=base_url)
        
        # Attempt model discovery if enabled
        if discover_models:
            self._discover_models()
        
        # OCR extraction prompt
        self.ocr_prompt = """
Extract all rows from this handwritten attendance register.

Return ONLY valid JSON.

Format:

[
  {
    "id": "SAR41",
    "name": "SHANKARAPPA"
  }
]

Rules:

- Extract only ID NO and EMP NAME.
- Ignore SL NO.
- Ignore Post Name.
- Ignore signatures.
- Ignore timings.
- Ignore comments.
- Ignore all other columns.
- Return raw JSON only.
"""
    
    def _discover_models(self):
        """Attempt to discover available models from provider."""
        try:
            models = self.gemini_client.list_models()
            if models:
                for m in models:
                    logging.info(
                        f"MODEL_FORMAT_DEBUG: Available: name='{m.get('name')}' "
                        f"display='{m.get('display_name')}' "
                        f"vision={m.get('supports_vision')}"
                    )
                current = config.get_gemini_model()
                raw_names = [m.get('name', '') for m in models]
                normalized = [GeminiClient.normalize_model_name(m.get('name', '')) for m in models]
                all_variants = set(raw_names + normalized)
                if current in all_variants:
                    logging.info(f"Configured model '{current}' is available")
                else:
                    logging.warning(f"Configured model '{current}' not found in available models")
            else:
                logging.info("Provider does not support model discovery")
        except Exception as e:
            logging.warning(f"Model discovery skipped: {e}")
    
    def extract_attendance_from_image(self, image_path: str) -> Tuple[List[Dict], str]:
        """
        Extract attendance attendance data from a single image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (extracted_data, raw_response)
            extracted_data: List of dicts with 'id' and 'name' keys
            raw_response: Raw response from Gemini for debugging
            
        Raises:
            OCRServiceException: If extraction fails
        """
        try:
            # Load and validate image
            image = self._load_image(image_path)
            
            # Call Gemini Client
            raw_response = self.gemini_client.generate_content(
                prompt=self.ocr_prompt,
                images=[image]
            )
            
            logging.info(f"Gemini raw response: {raw_response}")
            
            # Parse JSON response
            extracted_data = self._parse_gemini_response(raw_response)
            
            logging.info(f"Successfully extracted {len(extracted_data)} employees from {image_path}")
            
            return extracted_data, raw_response
            
        except Exception as e:
            logging.error(f"OCR extraction failed for {image_path}: {e}")
            raise OCRServiceException(f"Failed to extract attendance from {image_path}: {e}")
    
    def extract_attendance_from_images(self, image_paths: List[str]) -> Tuple[List[Dict], List[str]]:
        """
        Extract attendance data from multiple images.
        
        Args:
            image_paths: List of paths to image files
            
        Returns:
            Tuple of (all_extracted_data, all_raw_responses)
            all_extracted_data: Combined list of all extracted employees
            all_raw_responses: List of raw responses for debugging
        """
        all_extracted_data = []
        all_raw_responses = []
        
        for image_path in image_paths:
            try:
                extracted_data, raw_response = self.extract_attendance_from_image(image_path)
                all_extracted_data.extend(extracted_data)
                all_raw_responses.append(f"Image: {image_path}\nResponse: {raw_response}")
                
            except OCRServiceException as e:
                logging.error(f"Failed to process {image_path}: {e}")
                all_raw_responses.append(f"Image: {image_path}\nError: {str(e)}")
                # Continue processing other images
                continue
        
        logging.info(f"Total extracted employees from {len(image_paths)} images: {len(all_extracted_data)}")
        
        return all_extracted_data, all_raw_responses
    
    def _load_image(self, image_path: str) -> Image.Image:
        """
        Load and validate image file.
        
        Args:
            image_path: Path to image file
            
        Returns:
            PIL Image object
            
        Raises:
            OCRServiceException: If image loading fails
        """
        try:
            path = Path(image_path)
            
            if not path.exists():
                raise OCRServiceException(f"Image file not found: {image_path}")
            
            if not path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                raise OCRServiceException(f"Unsupported image format: {path.suffix}")
            
            # Load image
            image = Image.open(path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Check image size (Gemini has limits)
            max_size = (4096, 4096)  # Gemini's typical limit
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                logging.warning(f"Resizing large image: {image.size} -> {max_size}")
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            raise OCRServiceException(f"Failed to load image {image_path}: {e}")
    
    def _parse_gemini_response(self, raw_response: str) -> List[Dict]:
        """
        Parse Gemini's JSON response into structured data.
        
        Args:
            raw_response: Raw text response from Gemini
            
        Returns:
            List of employee dictionaries with 'id' and 'name' keys
            
        Raises:
            OCRServiceException: If JSON parsing fails
        """
        try:
            # Clean the response - remove any markdown formatting
            cleaned_response = raw_response.strip()
            
            # Remove potential markdown code block markers
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            cleaned_response = cleaned_response.strip()
            
            # Parse JSON
            parsed_data = json.loads(cleaned_response)
            
            # Validate structure
            if not isinstance(parsed_data, list):
                raise OCRServiceException("Response is not a JSON array")
            
            validated_data = []
            for item in parsed_data:
                if not isinstance(item, dict):
                    logging.warning(f"Skipping non-dict item: {item}")
                    continue
                
                if 'id' not in item or 'name' not in item:
                    logging.warning(f"Skipping item missing id/name: {item}")
                    continue
                
                # Clean the data
                clean_item = {
                    'id': str(item['id']).strip().upper(),
                    'name': str(item['name']).strip().upper()
                }
                
                # Skip empty entries
                if not clean_item['id'] or not clean_item['name']:
                    logging.warning(f"Skipping empty item: {clean_item}")
                    continue
                
                validated_data.append(clean_item)
            
            return validated_data
            
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing failed. Raw response: {raw_response}")
            raise OCRServiceException(f"Invalid JSON response from Gemini: {e}")
        
        except Exception as e:
            logging.error(f"Response parsing failed: {e}")
            raise OCRServiceException(f"Failed to parse Gemini response: {e}")
    
    def test_connection(self, model: Optional[str] = None,
                        provider: Optional[str] = None,
                        base_url: Optional[str] = None) -> Dict:
        """
        Test Gemini API connection (optionally with a different model).

        Returns:
            Dict with keys: success (bool), latency (float seconds),
            model (str), error (str or None)
        """
        if model or provider or base_url:
            client = GeminiClient(
                api_key=self.gemini_client.api_key,
                model=model, provider=provider, base_url=base_url
            )
        else:
            client = self.gemini_client

        test_model = model or config.get_gemini_model()
        start = time.time()
        try:
            response = client.generate_content("Test connection. Respond with 'OK'.")
            latency = time.time() - start
            return {
                "success": "OK" in response.upper(),
                "latency": round(latency, 2),
                "model": test_model,
                "error": None,
            }
        except Exception as e:
            latency = time.time() - start
            return {
                "success": False,
                "latency": round(latency, 2),
                "model": test_model,
                "error": str(e),
            }


class OCRServiceException(Exception):
    """Custom exception for OCR service errors."""
    pass


# Utility functions for OCR processing

def validate_image_files(file_paths: List[str]) -> List[str]:
    """
    Validate image file paths and return only valid ones.
    
    Args:
        file_paths: List of file paths to validate
        
    Returns:
        List of valid image file paths
    """
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    valid_files = []
    
    for file_path in file_paths:
        try:
            path = Path(file_path)
            if path.exists() and path.suffix.lower() in valid_extensions:
                valid_files.append(file_path)
            else:
                logging.warning(f"Skipping invalid image file: {file_path}")
        except Exception as e:
            logging.warning(f"Error validating file {file_path}: {e}")
    
    return valid_files


def estimate_processing_time(image_count: int) -> int:
    """
    Estimate OCR processing time in seconds.
    
    Args:
        image_count: Number of images to process
        
    Returns:
        Estimated time in seconds
    """
    # Rough estimate: 10-20 seconds per image depending on complexity
    base_time_per_image = 15
    return image_count * base_time_per_image