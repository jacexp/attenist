# Windows Deployment

## Files Added

| File | Purpose |
|------|---------|
| `requirements.txt` | All 5 runtime dependencies |
| `setup.bat` | One-click environment setup (venv + deps + verify) |
| `Start.bat` | One-click launch (auto-runs setup if needed) |
| `README_WINDOWS.md` | User-facing Windows instructions |

---

## `requirements.txt`

```
openpyxl>=3.1.5
pyside6>=6.11.1
rapidfuzz>=3.14.5
pillow>=12.0.0
google-genai>=2.0.0
```

Confirmed by scanning every `.py` file in the project for third-party imports.

### Usage Map

| Package | Used In |
|---------|---------|
| `openpyxl` | `workbook/loader.py`, `workbook/detector.py` |
| `pyside6` | `main.py`, `ui/main_window.py`, `ui/ocr_attendance_tab.py`, `ui/employee_management_tab.py`, `ui/api_key_dialog.py` |
| `rapidfuzz` | `services/search_service.py`, `services/ocr/validation_service.py` |
| `pillow` (as `PIL`) | `services/gemini_client.py`, `services/ocr/ocr_service.py` |
| `google-genai` (as `google.genai`) | `services/gemini_client.py` |

---

## `setup.bat` Step-by-Step

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: Check Python                                  │
│  python --version                                      │
│  → If missing: show download URL, pause, exit          │
├─────────────────────────────────────────────────────────┤
│  Step 2: Display Python version                        │
│  → "Python 3.12.4 detected."                           │
├─────────────────────────────────────────────────────────┤
│  Step 3: Create virtual environment (if missing)       │
│  → "Creating virtual environment..." / "Done."         │
├─────────────────────────────────────────────────────────┤
│  Step 4: Activate venv                                 │
│  → call venv\Scripts\activate.bat                      │
├─────────────────────────────────────────────────────────┤
│  Step 5: Upgrade pip                                   │
│  → python -m pip install --upgrade pip                 │
├─────────────────────────────────────────────────────────┤
│  Step 6: Install requirements                          │
│  → pip install -r requirements.txt                     │
│  → Shows full pip download/install progress            │
├─────────────────────────────────────────────────────────┤
│  Step 7: Verify critical imports                       │
│  → python -c "import PySide6, openpyxl, rapidfuzz,     │
│               PIL; from google import genai"           │
│  → Success: "Installation successful."                │
│  → Failure: lists which packages failed                │
├─────────────────────────────────────────────────────────┤
│  Step 8: pause before exit                             │
└─────────────────────────────────────────────────────────┘
```

---

## `Start.bat` Step-by-Step

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: Change to project directory                   │
│  → cd /d %~dp0                                         │
├─────────────────────────────────────────────────────────┤
│  Step 2: If venv missing → auto-run setup.bat          │
│  → if not exist venv\Scripts\python.exe call setup.bat │
│  → If setup fails: show error, pause, exit             │
├─────────────────────────────────────────────────────────┤
│  Step 3: Activate venv                                 │
│  → call venv\Scripts\activate.bat                      │
├─────────────────────────────────────────────────────────┤
│  Step 4: Launch application                            │
│  → "Starting Attenist..."                              │
│  → python main.py                                      │
├─────────────────────────────────────────────────────────┤
│  Step 5: Handle unexpected exit                        │
│  → if errorlevel ≠ 0: show error code                  │
│  → pause before closing window                         │
└─────────────────────────────────────────────────────────┘
```

---

## API Key Handling

The application never requires environment variables.

```
NEVER:  export GEMINI_API_KEY=...
NEVER:  set GEMINI_API_KEY=...
NEVER:  .env file
```

API key is managed entirely through `config.json`:

```json
{
    "gemini_api_key": "your-key-here",
    "gemini_provider": "google",
    "gemini_base_url": "",
    "gemini_model": "gemini-flash-latest",
    "app_version": "2.0.0"
}
```

On first launch, if no API key is found, the application shows a setup dialog.
The user enters their key in the UI. It is saved to `config.json`.

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Fresh machine: clone → double-click setup.bat | Automated |
| Python missing → clear error with download URL | ✓ |
| venv created automatically | ✓ |
| Dependencies installed from requirements.txt | ✓ |
| Imports verified after install | ✓ |
| Start.bat works without prior setup.bat run | ✓ (auto-setup) |
| No manual pip install required | ✓ |
| No manual venv creation required | ✓ |
| No GEMINI_API_KEY env var required | ✓ |
| App crash shows traceback | ✓ |
| Clear terminal messages at every step | ✓ |

---

## Files Delivered

```
project_root/
├── requirements.txt          # NEW — pip dependencies
├── setup.bat                 # NEW — one-click setup
├── Start.bat                 # UPDATED — auto-setup + error handling
├── docs/README_WINDOWS.md    # Windows instructions
├── docs/
│   └── WINDOWS_DEPLOYMENT.md # THIS FILE
└── ... (existing project files)
```
