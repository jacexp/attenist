# Attenist — Windows Deployment

## Files Added

| File | Purpose |
|------|---------|
| `requirements.txt` | All runtime dependencies for pip install |
| `setup.bat` | One-click environment setup (venv + deps) |
| `Start.bat` | One-click launch (auto-setup if needed) |
| `README_WINDOWS.md` | This file |

---

## `requirements.txt`

```
openpyxl>=3.1.5
pyside6>=6.11.1
rapidfuzz>=3.14.5
pillow>=12.0.0
google-genai>=2.0.0
```

Five packages, all confirmed by scanning every Python file in the project.

---

## `setup.bat` Flow

```
Step 1:  Check Python availability
         → If missing: show ERROR with download URL, pause, exit

Step 2:  Display detected version
         → e.g., "Python 3.12.4 detected."

Step 3:  Create virtual environment (if venv/ missing)
         → python -m venv venv
         → "Creating virtual environment..." / "Done."

Step 4:  Activate venv
         → call venv\Scripts\activate.bat

Step 5:  Upgrade pip
         → python -m pip install --upgrade pip

Step 6:  Install requirements
         → pip install -r requirements.txt
         → Shows full pip progress output

Step 7:  Verify critical imports
         → python -c "import PySide6, openpyxl, rapidfuzz, PIL; from google import genai"
         → Success:  "Installation successful. Attenist is ready to use."
         → Failure:  Lists which package(s) failed to import

Step 8:  pause
```

---

## `Start.bat` Flow

```
1. cd to project directory
2. If venv/ missing → run setup.bat automatically
3. Activate venv
4. Launch: python main.py
5. If application exits with error → show traceback and pause
6. Always pause before exit
```

---

## API Key Handling

The application never requires `GEMINI_API_KEY` environment variable.

API key is managed through the application UI and stored in `config.json`:

```json
{
    "gemini_api_key": "your-key-here",
    "gemini_provider": "google",
    "gemini_base_url": "",
    "gemini_model": "gemini-flash-latest",
    "app_version": "2.0.0"
}
```

On first launch without a key, the app shows an API key dialog.
No environment variables needed.

---

## Installation

1. Clone or unzip the project.
2. Double-click `setup.bat`.
3. Wait for installation to complete (60–120 seconds).
4. Double-click `Start.bat`.

## Daily Use

- Double-click `Start.bat`.

## Updating

- Run `setup.bat` again to refresh dependencies.

---

## Validation

| Step | Expected Result |
|------|----------------|
| Python not found | Error message with download URL |
| Python found | Version displayed |
| venv created | "Done." |
| pip upgrade | No errors |
| pip install | Dependencies download and install |
| Import check | "Installation successful." or failing package listed |
| Start.bat without venv | Auto-runs setup.bat |
| Start.bat with venv | App launches |
| App crashes | Error code displayed, paused |
