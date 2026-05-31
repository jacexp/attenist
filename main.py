import sys

from PySide6.QtWidgets import QApplication, QFileDialog

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # Workbook Selection
    file_path, _ = QFileDialog.getOpenFileName(
        None,
        "Open Attendance Workbook",
        "",
        "Excel Files (*.xlsx)"
    )

    if not file_path:
        return

    window = MainWindow(file_path)

    window.adjustSize()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()