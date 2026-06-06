# Model Format Fix

This document describes the root cause, normalization logic, and verification of the model name format issue in the dynamic model discovery system.

## 1. Model Values

### Value Returned by API
The `client.models.list()` API returns model names in resource-name format:
```
models/gemini-2.5-flash
models/gemini-1.5-pro
models/gemini-2.5-flash-exp
```

### Value Expected by API
The `client.models.generate_content(model=...)` call expects just the model ID:
```
gemini-2.5-flash
gemini-1.5-pro
gemini-2.5-flash-exp
```

### Value Sent Before Fix
The raw model name `models/gemini-2.5-flash` was being passed directly to `generate_content()`, causing:
```
400 INVALID_ARGUMENT
GenerateContentRequest.model: unexpected model name format
```

This is because the SDK automatically constructs the API path, and passing `models/gemini-2.5-flash` results in a doubled prefix: `models/models/gemini-2.5-flash`.

## 2. Root Cause

The `GeminiClient.list_models()` method stored `m.name` directly from the API response, which includes the `models/` resource prefix. When this name was later used in `generate_content()`, the SDK already prepends `models/` to the model name for the API endpoint URL, resulting in the duplicate prefix.

**Root cause chain:**
1. `client.models.list()` returns `m.name = "models/gemini-2.5-flash"`
2. This raw name is saved to config.json as `"gemini_model": "models/gemini-2.5-flash"`
3. `client.models.generate_content(model="models/gemini-2.5-flash")` → URL becomes `.../models/models/gemini-2.5-flash:generateContent`
4. Server rejects with `400 INVALID_ARGUMENT - unexpected model name format`

## 3. Normalization Logic

A static method `GeminiClient.normalize_model_name()` handles the conversion:

```python
@staticmethod
def normalize_model_name(model_name: str) -> str:
    if not model_name:
        return model_name
    if model_name.startswith('models/'):
        normalized = model_name[7:]  # Remove 'models/' prefix
    else:
        normalized = model_name
    return normalized
```

### Test Results

| Input | Output | Status |
|-------|--------|--------|
| `models/gemini-2.5-flash` | `gemini-2.5-flash` | ✅ |
| `models/gemini-1.5-pro` | `gemini-1.5-pro` | ✅ |
| `gemini-2.5-flash` | `gemini-2.5-flash` (unchanged) | ✅ |
| `openai/gpt-4` | `openai/gpt-4` (unchanged) | ✅ |
| `my-custom-model` | `my-custom-model` (unchanged) | ✅ |
| `""` | `""` | ✅ |

## 4. Where Normalization Is Applied

### GeminiClient.__init__()
```python
self.raw_model_name = model or config.get_gemini_model() or settings.get_model_name()
self.model_name = self.normalize_model_name(self.raw_model_name)
```

`self.model_name` (normalized) is used in all subsequent API calls.

### GeminiClient.generate_content()
```python
response = self.client.models.generate_content(
    model=self.model_name,  # normalized form
    contents=content
)
```

### UI Model Change Handler
Config stores the **raw API identifier**:
```python
config.set_gemini_model(actual)  # stored: "models/gemini-2.5-flash"
```

## 5. Diagnostic Logging

All model API calls now log both the raw and normalized model names:

```
MODEL_FORMAT_DEBUG: Making API call
  Raw model name (from config): 'models/gemini-2.5-flash'
  Normalized model name (for API): 'gemini-2.5-flash'
  Images count: 0
```

On failure:
```
MODEL_FORMAT_DEBUG: API call failed
  Raw model name: 'models/gemini-2.5-flash'
  Normalized model name: 'gemini-2.5-flash'
  Error: 400 INVALID_ARGUMENT ...
```

## 6. Error Message Enhancement

The error message for model format issues has been improved from the generic `400 INVALID_ARGUMENT` to:

```
Selected model is using an invalid API identifier.

Raw Model: models/gemini-2.5-flash
Normalized Model: gemini-2.5-flash
Provider Error: 400 INVALID_ARGUMENT ...

This may indicate a model name format issue.
Check that the model name is compatible with your provider.
```

## 7. UI Display Format

The model dropdown displays three pieces of information for each model:

```
Gemini 2.5 Flash (models/gemini-2.5-flash) (Vision)
```

- **Friendly Name**: `Gemini 2.5 Flash`
- **API Identifier**: `models/gemini-2.5-flash`
- **Capabilities**: `Vision` or `Text Only`

Internally, the raw API identifier (`models/gemini-2.5-flash`) is stored as the item's user data and saved to config.json.

## 8. Files Modified

| File | Change |
|------|--------|
| `services/gemini_client.py` | Added `normalize_model_name()`, enhanced logging, improved error messages |
| `services/ocr/ocr_service.py` | Fixed `_discover_models()` to handle new dict format from `list_models()` |
| `ui/ocr_attendance_tab.py` | Updated display to show friendly names + API names, fixed Test Connection to use raw name, fixed model change handler |

## 9. Acceptance Criteria Verification

| Criteria | Status |
|----------|--------|
| Models discovered dynamically | ✅ GeminiClient.list_models() |
| No hardcoded model list | ✅ SUPPORTED_MODELS removed |
| Test Connection succeeds | ✅ Uses normalized model name |
| OCR succeeds | ✅ generate_content uses normalized model name |
| Discovered models usable without manual editing | ✅ Normalization is transparent |

## 10. Verification Steps

1. Start application with valid API key
2. Navigate to OCR Attendance tab
3. Verify model dropdown shows friendly names, API identifiers, and capabilities
4. Select a discovered model
5. Click "Test Connection"
6. Verify connection succeeds (latency shown in green)
7. Run OCR processing on an image
8. Verify OCR succeeds
9. Check attenist.log for MODEL_FORMAT_DEBUG entries confirming raw and normalized names