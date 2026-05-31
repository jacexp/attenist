# Attenist

Attenist is a high-performance desktop attendance assistant designed for rapid data entry into existing Microsoft Excel workbooks. It is built for operators who need to process hundreds of employees quickly while maintaining data integrity and auditability.

## Features

- **Multi-Sheet Indexing**: Automatically scans all worksheets in a workbook to find employees across different departments or sections.
- **Global Fuzzy Search**: Search by Employee ID or Name across the entire organization.
- **Instant Attendance Marking**: In-memory updates ensure that data entry is instantaneous, even with large workbooks.
- **Change Summary Panel**: A live view of all pending changes before they are committed to disk.
- **Voice Confirmation**: Background audio feedback speaks the employee's name upon marking to confirm accuracy without looking away from the search box.
- **Keyboard-First Workflow**: Optimized for speed with full keyboard support (Enter to mark, Ctrl+S to save).
- **Data Integrity**: Uses atomic save strategies (temp file swap) and automatic pre-save backups (`.bak`) to protect the source of truth.
- **Audit Logging**: Every change is logged with a timestamp and "before/after" values in `attenist.log`.

## Installation

### Prerequisites

- Python 3.10+ (Current project specifies 3.14)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd attenist
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   uv pip install -e .
   ```
   Or using pip:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   pip install -r pyproject.toml
   ```

## Running the Application

Start the application by running:
```bash
python main.py
```

Upon startup, you will be prompted to select an attendance workbook (`.xlsx`).

### Controls

- **Search**: Focuses automatically on startup. Type Employee ID or Name.
- **Select Match**: Use **Up/Down Arrow Keys** to select from multiple matches.
- **Focus Shift**: Press **Enter** in the Search box to move focus to the Shift dropdown.
- **Mark Attendance**: Press **Enter** while the Shift dropdown has focus, or click the **Mark Attendance** button.
- **Save Workbook**: Press **Ctrl+S** or click the **Save Workbook** button.
- **Exit**: Close the window. If you have unsaved changes, you will be prompted to save or discard them.

## Workflow

### Attendance Entry
1. Open a workbook.
2. Search for an employee.
3. Select the correct match from the list.
4. Choose the shift and press **Enter**.
5. The name is spoken, the summary panel updates, and focus returns to the search box for the next employee.

### Manual Save Workflow
Attenist uses in-memory writes to keep entry fast. Changes are NOT written to the Excel file until you trigger a save.
- Use the **Pending Changes Summary** on the right to review your work.
- Use **Ctrl+S** to commit all changes to disk in one atomic operation.
- A backup (`.bak`) is created automatically before the first save of each session.

## Platform Specifics

### Windows Usage
- Fully supported.
- **Note**: If the Excel file is open in Microsoft Excel, Attenist will be unable to save. Close the file in Excel before saving in Attenist.

### Linux Usage
- Fully supported.
- Ensure you have the necessary speech synthesis libraries installed for `pyttsx3` (e.g., `espeak` or `nsss`).

## Known Limitations

- **Excel Locks**: Cannot write to files that are currently open in Microsoft Excel on Windows.
- **Atomic Save**: Atomic file swapping is only guaranteed when the temporary directory and the workbook are on the same filesystem partition.
- **Voice Confirmation**: Requires local TTS engines to be configured on the host OS.
