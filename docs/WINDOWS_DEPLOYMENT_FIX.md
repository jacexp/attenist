# Windows Deployment Fix Report

## Overview
This report documents the design and implementation of a production-grade Windows launch experience for Attenist V2.0. This fix resolves issues where the batch launcher assumed incorrect directory names, failed to handle the Gemini API key seamlessly, and required manual environment variable configuration or CLI editing.

---

## 1. Fixed Startup & Launch Flow

### Old Startup Flow (Broken)
```
Double-click Start.bat (tries .venv) 
→ Fails if using "venv" 
→ If starts, OCR initializes immediately 
→ Crashes with ValueError if GOOGLE_API_KEY environment variable is not exported
```

### New Launch Flow (Production-Grade)
```
Double-click Start.bat (correctly uses "venv")
→ Main window loads 
→ ConfigManager checks config.json
→ If key missing:
    ├── FirstLaunchManager displays key configuration dialog
    ├── User enters key and clicks Save
    └── Key saved persistently in config.json
→ Main window launches 
→ OCR tab initializes safely:
    ├── If key present: OCR starts normally
    └── If key missing: OCR features are disabled, shows "Configure Gemini API Key" button
```

---

## 2. Config & Key Management Design (`core/config.py`)

A persistent JSON-based settings manager has been introduced:
- **`config.json`**: Created automatically on first startup.
- **Keys tracked**:
  - `gemini_api_key`: Persistent encrypted/cleartext key store.
  - `gemini_provider`: Gateway provider (default: `google`).
  - `gemini_base_url`: Gateway custom URL.
  - `gemini_model`: Specific model string.
- **Safety**: Never logs the raw API key to application logs or stdout.

---

## 3. UI Components Implemented

### First-Launch Dialog (`ui/api_key_dialog.py`)
Provides an interactive, non-technical wizard for users:
- **Title**: Welcome to Attenist OCR.
- **Instructions**: Clean guide on getting a Gemini key from Google AI Studio.
- **Masked Input**: Password echo mode to keep API keys secure during entry (with a "Show key" toggle checkbox).
- **Advanced Options**: Expanding section allowing users to override providers, models, and custom gateway endpoints (for gateways like OpenRouter or LiteLLM).

### Safe OCR Tab Loader (`ui/ocr_attendance_tab.py`)
Ensures startup stability:
- **No-Crash Guarantee**: If `config.json` doesn't have an API key, the OCR tab loads gracefully rather than throwing a crash.
- **Disabled State**: Browse and process buttons are disabled and a prominent "Configure Gemini API Key" button is rendered.
- **Hot Reload**: Once the key is configured, the OCR tab initializes the models in real-time **without requiring a application restart**.

---

## 4. Startup Diagnostics

At application startup, the OCR tab prints a diagnostic header:

```
=== OCR Startup Diagnostics ===
Config file found: True
API key configured: True (or False)
OCR enabled: True (or False)
==================================
```

---

## 5. Start.bat Realization

The batch file has been fully normalized to work with standard Python environments:

```bat
@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Please run setup first or ensure 'venv' folder exists.
    pause
    exit /b 1
)

venv\Scripts\python.exe main.py

pause
```

---

## 6. Files Changed

| File | Change Type | Description |
|:---|:---|:---|
| `Start.bat` | **Fixed** | Updated to resolve virtual env from `venv` and cd to project root safely. |
| `core/config.py` | **Created** | High-level `config.json` schema, read/write helper, and automatic creator. |
| `ui/api_key_dialog.py` | **Created** | Non-technical first-launch wizard and dialog framework. |
| `ui/ocr_attendance_tab.py` | **Modified** | Refactored initialization to handle key-missing states, hot-reloading, and diagnostics. |
| `ui/main_window.py` | **Modified** | Imported and triggered the `FirstLaunchManager` check on initialization. |

---

## 7. Non-Technical Windows Verification Plan

### Test Case 1: First-Time User Experience
1. **Prepare**: Delete existing `config.json` and ensure no `GOOGLE_API_KEY` is in the env.
2. **Execute**: Double-click `Start.bat`.
3. **Observation**:
   - Application launches quickly.
   - An intuitive "Configure Gemini API Key" dialog pops up.
   - User pastes key, clicks "Save & Enable OCR".
   - Main window becomes active, OCR tab shows "Gemini API: Ready".

### Test Case 2: Subsequent Launch
1. **Execute**: Double-click `Start.bat` again.
2. **Observation**:
   - Application launches immediately.
   - No dialog pops up.
   - OCR tab loads with "Gemini API: Ready" status instantly.

### Test Case 3: Error / Missing Key Graceful Handling
1. **Prepare**: In the dialog, click "Cancel" without entering a key.
2. **Observation**:
   - Application stays open and works.
   - OCR tab shows "Gemini API: Not Configured".
   - Process/Browse buttons are disabled.
   - "Configure Gemini API Key" button is clearly visible.
   - User can click the button, paste a key, and use the feature instantly.
