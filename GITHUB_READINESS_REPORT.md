# GITHUB_READINESS_REPORT.md

## 1. FILES SAFE TO COMMIT

The following files constitute the core application logic and configuration:

*   **`main.py`**: Application entry point.
*   **`pyproject.toml`**: Project metadata and dependency definitions.
*   **`uv.lock`**: Deterministic dependency lock file.
*   **`.python-version`**: Specifies the required Python version.
*   **`core/`**: Data models and shared exceptions.
*   **`services/`**: Business logic (Search, Attendance, Speech).
*   **`ui/`**: GUI implementation (MainWindow).
*   **`workbook/`**: Excel parsing and indexing logic.
*   **`README.md`**: Project documentation and setup guide.
*   **`.gitignore`**: Git exclusion rules.

## 2. FILES EXCLUDED FROM COMMIT

The following files have been added to `.gitignore` and must **NOT** be pushed to the repository:

*   **`*.xlsx`**: Attendance workbooks (Source of truth/Sensitive data).
*   **`*.bak`**: Automated backups created by Attenist.
*   **`*.log`**: Audit logs containing employee names and actions.
*   **`.venv/`**: Local virtual environment.
*   **`__pycache__/`**, **`*.pyc`**: Python byte-code caches.
*   **`samples/test_output.xlsx`**: Artifacts from diagnostic testing.
*   **OS-specific files**: `.DS_Store`, `Thumbs.db`, etc.

## 3. REQUIRED REPOSITORY STRUCTURE

```text
attenist/
├── core/
│   ├── exceptions.py
│   └── models.py
├── services/
│   ├── attendance_service.py
│   ├── search_service.py
│   └── speech_service.py
├── ui/
│   └── main_window.py
├── workbook/
│   ├── indexes/
│   │   ├── date.py
│   │   └── employee.py
│   ├── loader.py
│   └── ... (existing logic files)
├── .gitignore
├── .python-version
├── main.py
├── pyproject.toml
├── README.md
└── uv.lock
```

## 4. SETUP INSTRUCTIONS

1.  **Clone**: `git clone <private-repo-url>`
2.  **Environment**: 
    - Create a venv: `uv venv` or `python -m venv .venv`
    - Install: `uv pip install -e .` or `pip install -r pyproject.toml`
3.  **Run**: `python main.py`
4.  **Workbook**: Select a valid attendance `.xlsx` file when prompted.

## 5. REMAINING ISSUES BEFORE PUBLISHING

*   **Python Version**: The project currently specifies `requires-python = ">=3.14"` in `pyproject.toml` and `3.14` in `.python-version`. Since Python 3.14 is not yet released (current stable is 3.13), this should likely be changed to `3.10`, `3.11`, or `3.12` to allow developers to actually run the code.
*   **Documentation Files**: There are several `.md` reports in the root and `docs/` folder created during the development/review phase (e.g., `DATA_MODEL_DECISION.md`, `PRODUCTION_BLOCKERS.md`). 
    - *Recommendation*: Move these into a `docs/archive/` folder if you wish to keep the history, or delete them for a cleaner initial commit.
*   **Bat Files**: `Start.bat` and `debug.bat` are present in the root. If these contain hardcoded paths or local environment specifics, they should be removed or added to `.gitignore`.
