from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt


class AddBinDialog(QDialog):
    def __init__(self, parent=None, viewmodel=None):
        super().__init__(parent)
        self.vm = viewmodel
        self.setWindowTitle("Add Bin")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Part:"))
        self.input = QLineEdit()
        row.addWidget(self.input)
        layout.addLayout(row)

        self.results = QTableWidget(0, 2)
        self.results.setHorizontalHeaderLabels(["Part", "Name"])
        layout.addWidget(self.results)

        btns = QHBoxLayout()
        self.ok = QPushButton("OK")
        self.ok.setEnabled(False)
        cancel = QPushButton("Cancel")
        btns.addStretch()
        btns.addWidget(self.ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

        self.input.textChanged.connect(self._update_matches)
        self.results.cellClicked.connect(self._on_result_click)
        self.ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

        # suppression flag used when programmatically setting text to avoid
        # triggering autocomplete/update recursion
        self._suppress_autocomplete = False

    def _update_matches(self, text: str):
        if self._suppress_autocomplete:
            return

        self.results.setRowCount(0)
        if not text:
            self.ok.setEnabled(False)
            return
        # request up to 101 results so we can show 100 results + ellipsis
        rows = self.vm.prefix_matches(text, limit=101)
        for part, name in rows[:100]:
            r = self.results.rowCount()
            self.results.insertRow(r)
            self.results.setItem(r, 0, QTableWidgetItem(part))
            self.results.setItem(r, 1, QTableWidgetItem(name))
        if len(rows) > 100:
            r = self.results.rowCount()
            self.results.insertRow(r)
            self.results.setItem(r, 0, QTableWidgetItem("..."))
            self.results.setItem(r, 1, QTableWidgetItem(""))
        single = len(rows) == 1
        if single:
            only = rows[0][0]
            if only and only.startswith(text) and only != text:
                try:
                    self._suppress_autocomplete = True
                    self.input.setText(only)
                finally:
                    self._suppress_autocomplete = False
                self.ok.setEnabled(True)
                return

        # enable OK only when there's an exact match
        self.ok.setEnabled(self.vm.part_exists(text))

    def _on_result_click(self, row, col):
        item = self.results.item(row, 0)
        if not item:
            return
        if item.text() == "...":
            return
        part = item.text()
        if not part:
            return
        try:
            self._suppress_autocomplete = True
            self.input.setText(part)
            self.input.setSelection(len(part), 0)
            self.input.setFocus()
            self.ok.setEnabled(True)
        finally:
            self._suppress_autocomplete = False

    @staticmethod
    def getText(parent=None, viewmodel=None):
        dlg = AddBinDialog(parent=parent, viewmodel=viewmodel)
        accepted = dlg.exec() == QDialog.Accepted
        return (dlg.input.text(), accepted)
    