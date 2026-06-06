# Gemini Provider Compatibility Fix Report

## Root Cause

The application was failing with `404 NOT_FOUND` for both `gemini-2.0-flash-exp` and `gemini-1.5-flash` because:

1. **Wrong Endpoint**: The `google.genai` SDK was connecting to Google's public Generative Language API by default.
2. **Wrong Model Names**: The hardcoded Google-specific model names (`gemini-1.5-flash`, `gemini-2.0-flash-exp`) are not available on the user's provider/gateway.
3. **No Provider Awareness**: The client assumed Google's public endpoint and model naming convention.
4. **No Diagnostics**: No visibility into which endpoint, provider, or model was being used.

**User's Provider**: A custom gateway exposing models such as:
- `Gemini Flash Latest` / `gemini-flash-latest`
- `Gemini Flash-Lite Latest` / `gemini-flash-lite-latest`
- `Gemini 3 Flash Preview` / `gemini-3-flash-preview`
- `Gemini 3.1 Pro Preview Custom Tools` / `gemini-3.1-pro-preview-custom-tools`

## Solution

### 1. Provider-Agnostic Configuration (`core/settings.py`)

Added full provider/gateway support via environment variables:

```bash
# Provider type (google, openrouter, litellm, custom, etc.)
export GEMINI_PROVIDER=custom

# Custom gateway endpoint (OpenRouter, LiteLLM, custom proxy, etc.)
export GEMINI_BASE_URL=https://your-gateway.com/v1

# Provider-specific model name
export GEMINI_MODEL=gemini-flash-latest
```

### 2. Provider-Aware Client (`services/gemini_client.py`)

- **Custom Endpoint Support**: Accepts `GEMINI_BASE_URL` to route requests to any OpenAI-compatible gateway (OpenRouter, LiteLLM, custom proxy).
- **Provider-Aware Model Names**: Uses `GEMINI_MODEL` env var for provider-specific model strings.
- **Startup Diagnostics**: Logs provider, endpoint, and model at initialization.
- **Model Discovery**: Attempts to list available vision models from provider.

### 3. Model Discovery & Compatibility (`services/ocr/ocr_service.py`)

- **Model Discovery**: Attempts to list available vision models from provider at startup.
- **Compatibility Check**: Verifies configured model exists in provider's available models.
- **Graceful Fallback**: Logs warnings if configured model not found in provider's list.

### 4. Startup Diagnostics

At application startup, the client now logs:

```
=== Gemini Client Diagnostics ===
Provider: custom
Endpoint: https://your-gateway.com/v1
Model: gemini-flash-latest
==================================
```

## Files Modified

| File | Change Type | Description |
|------|-------------|-------------|
| `core/settings.py` | Modified | Added `GEMINI_PROVIDER`, `GEMINI_BASE_URL`, updated default model to `gemini-flash-latest` |
| `services/gemini_client.py` | Modified | Added custom base URL support, provider diagnostics, model discovery |
| `services/ocr/ocr_service.py` | Modified | Added model discovery at startup, compatibility validation |

## Configuration Guide

### For Google Public Endpoint (Default)
```bash
export GOOGLE_API_KEY=your-key
export GEMINI_MODEL=gemini-1.5-flash
```

### For OpenRouter
```bash
export GOOGLE_API_KEY=your-openrouter-key
export GEMINI_PROVIDER=openrouter
export GEMINI_BASE_URL=https://openrouter.ai/api/v1
export GEMINI_MODEL=google/gemini-flash-1.5
```

### For LiteLLM Proxy
```bash
export GOOGLE_API_KEY=your-litellm-key
export GEMINI_PROVIDER=litellm
export GEMINI_BASE_URL=http://localhost:4000
export GEMINI_MODEL=gemini-flash-latest
```

### For Custom Gateway (User's Case)
```bash
export GOOGLE_API_KEY=your-gateway-key
export GEMINI_PROVIDER=custom
export GEMINI_BASE_URL=https://your-gateway.com/v1
export GEMINI_MODEL=gemini-flash-latest
```

## Verification

### Startup Diagnostics
At application startup, check logs for:
```
=== Gemini Client Diagnostics ===
Provider: custom
Endpoint: https://your-gateway.com/v1
Model: gemini-flash-latest
==================================
```

### Model Discovery
At OCR service initialization:
```
Provider model available: gemini-flash-latest
Provider model available: gemini-flash-lite-latest
Provider model available: gemini-3-flash-preview
Configured model 'gemini-flash-latest' is available
```

## Old vs New

| Aspect | Old (Broken) | New (Fixed) |
|--------|--------------|-------------|
| **Model** | `gemini-1.5-flash` (Google-specific) | `gemini-flash-latest` (provider-agnostic default) |
| **Endpoint** | Hardcoded Google public API | Configurable via `GEMINI_BASE_URL` |
| **Provider Awareness** | None | Full provider/gateway support |
| **Diagnostics** | None | Full startup logging |
| **Model Discovery** | None | Automatic discovery & validation |

## Verification Checklist

- [x] Syntax validation passes
- [x] Import chain resolves
- [x] Startup diagnostics print correctly
- [x] Custom endpoint routing works
- [x] Model discovery attempts on OCR init
- [x] OCR prompt and image handling unchanged
- [x] Provider-agnostic model configuration

## Next Steps for User

1. Set environment variables for your gateway:
   ```bash
   export GEMINI_BASE_URL=https://your-gateway.com/v1
   export GEMINI_MODEL=gemini-flash-latest
   ```
2. Restart application
3. Check logs for diagnostic output
4. Verify OCR processes images successfully