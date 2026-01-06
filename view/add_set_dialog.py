from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QVBoxLayout, QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt
from model.db import create_connection

class AddSetDialog(QDialog):
    """Dialog that asks for a set number and only enables OK when the set exists in the `sets` table."""

    def __init__(self, parent=None, db_path: str = "data.db", title: str = "Add Set", label: str = "Set number:"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._db_path = db_path

        self._label = QLabel(label)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("e.g. 40743-1")

        # results table showing prefix matches (Set Number, Name)
        self._results = QTableWidget()
        self._results.setColumnCount(2)
        self._results.setHorizontalHeaderLabels(["Set", "Name"]) 
        self._results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._results.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._results.setEditTriggers(QTableWidget.NoEditTriggers)
        self._results.setSelectionBehavior(QTableWidget.SelectRows)
        self._results.setSelectionMode(QTableWidget.SingleSelection)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)

        v = QVBoxLayout(self)
        v.addWidget(self._label)
        v.addWidget(self._edit)
        v.addWidget(self._results)
        v.addWidget(self._buttons)

        self._edit.textChanged.connect(self._on_text_changed)
        self._results.cellClicked.connect(self._on_results_clicked)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        # implement starts-with autocomplete: if exactly one set starts with the prefix,
        # auto-complete the remainder and select it (like Google autocomplete).
        # Avoid recursion when we programmatically set text by using a guard.
        self._suppress_autocomplete = False

    def _on_text_changed(self, text: str):
        if self._suppress_autocomplete:
            return

        prefix = text.strip()
        ok_btn = self._buttons.button(QDialogButtonBox.Ok)
        if not prefix:
            ok_btn.setEnabled(False)
            return

        try:
            conn = create_connection(self._db_path)
            cur = conn.cursor()
            # fetch up to 101 matches to detect >100
            cur.execute("SELECT set_num, name FROM sets WHERE set_num LIKE ? ESCAPE '\\' LIMIT 101", (prefix + "%",))
            rows = cur.fetchall()
            conn.close()
        except Exception:
            rows = []

        # populate results table with up to 100 rows
        self._results.blockSignals(True)
        self._results.setRowCount(0)
        more = False
        if len(rows) > 100:
            more = True
            rows = rows[:100]
        for r in rows:
            row = self._results.rowCount()
            self._results.insertRow(row)
            item0 = QTableWidgetItem(r[0])
            item1 = QTableWidgetItem(r[1] or "")
            self._results.setItem(row, 0, item0)
            self._results.setItem(row, 1, item1)
        if more:
            # append ellipsis row
            row = self._results.rowCount()
            self._results.insertRow(row)
            item0 = QTableWidgetItem("...")
            item1 = QTableWidgetItem("")
            # style as disabled-looking by making it not selectable
            item0.setFlags(item0.flags() & ~Qt.ItemIsSelectable)
            item1.setFlags(item1.flags() & ~Qt.ItemIsSelectable)
            self._results.setItem(row, 0, item0)
            self._results.setItem(row, 1, item1)
        self._results.blockSignals(False)

        # if exactly one match, perform autocomplete like before
        if len(rows) == 1:
            match = rows[0][0]
            if match and match.startswith(prefix) and match != prefix:
                try:
                    self._suppress_autocomplete = True
                    self._edit.setText(match)
                    self._edit.setSelection(len(prefix), len(match) - len(prefix))
                finally:
                    self._suppress_autocomplete = False
                ok_btn.setEnabled(True)
                return

        # otherwise enable OK only when there's an exact match in sets (check first 100)
        exact = any(r[0] == prefix for r in rows)
        ok_btn.setEnabled(exact)

    @staticmethod
    def getText(parent, db_path: str, title: str, label: str):
        dlg = AddSetDialog(parent=parent, db_path=db_path, title=title, label=label)
        accepted = dlg.exec() == QDialog.Accepted
        return (dlg._edit.text(), accepted)

    def _on_results_clicked(self, row, column):
        # ignore ellipsis row (first column '...')
        item = self._results.item(row, 0)
        if not item:
            return
        if item.text() == "...":
            return
        set_num = item.text()
        if not set_num:
            return
        try:
            self._suppress_autocomplete = True
            self._edit.setText(set_num)
            # select nothing; place cursor at end
            self._edit.setSelection(len(set_num), 0)
            self._edit.setFocus()
            # enable OK since user selected a valid set
            ok_btn = self._buttons.button(QDialogButtonBox.Ok)
            if ok_btn:
                ok_btn.setEnabled(True)
        finally:
            self._suppress_autocomplete = False
