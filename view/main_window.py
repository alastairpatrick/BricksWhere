from concurrent.futures import ThreadPoolExecutor
import logging
from PySide6.QtWidgets import QMainWindow, QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QVBoxLayout, QWidget, QHBoxLayout
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal, Qt
import sqlite3

logger = logging.getLogger(__name__)

from .sync_progress_dialog import SyncProgressDialog
from viewmodel import SyncViewModel
from viewmodel.sets_viewmodel import SetsViewModel


class MainWindow(QMainWindow):

    def __init__(self, db_path: str = "data.db", dialog_provider=None):
        super().__init__()
        self._db_path = db_path
        self._executor = ThreadPoolExecutor(max_workers=2)

        self.setWindowTitle("BricksWhere")

        # Menu -> Tools -> Resynchronize with Rebrickable
        tools = self.menuBar().addMenu("Tools")
        self.sync_action = QAction("Resynchronize with Rebrickable", self)
        self.sync_action.triggered.connect(self.start_sync)
        tools.addAction(self.sync_action)

        self._sync_vm = SyncViewModel(self._db_path, self._executor)
        # bottom tabs
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabPosition(QTabWidget.South)

        # Sets tab
        self._sets_tab = QWidget()
        sets_layout = QVBoxLayout(self._sets_tab)
        self._sets_table = QTableWidget()
        self._sets_table.setColumnCount(4)
        self._sets_table.setHorizontalHeaderLabels(["Set Number", "Name", "Quantity", "Remark"])
        self._sets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._sets_table.setSortingEnabled(True)
        sets_layout.addWidget(self._sets_table)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        self._add_set_btn = QPushButton("Add")
        self._del_set_btn = QPushButton("Delete")
        btn_layout.addWidget(self._add_set_btn)
        btn_layout.addWidget(self._del_set_btn)
        sets_layout.addWidget(btn_row)

        # Placeholder tab
        self._placeholder_tab = QWidget()

        self._tab_widget.addTab(self._sets_tab, "Sets")
        self._tab_widget.addTab(self._placeholder_tab, "Placeholder")

        # Use QMainWindow public API: set a central widget with a layout instead
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addWidget(self._tab_widget)
        self.setCentralWidget(central)

        self._sets_vm = SetsViewModel(self._db_path)

        # dialog provider is a callable(parent, title, label) -> (text, ok)
        if dialog_provider is None:
            def _default_dialog_provider(parent, title, label):
                # use AddSetDialog which validates existence in the sets table
                from .add_set_dialog import AddSetDialog

                return AddSetDialog.getText(parent, self._db_path, title, label)

            self._dialog_provider = _default_dialog_provider
        else:
            self._dialog_provider = dialog_provider

        # populate initial sets table
        self._populate_sets_table()

        # wire up sets table handlers
        self._sets_table.itemChanged.connect(self._on_sets_item_changed)
        self._add_set_btn.clicked.connect(self._on_add_set)
        self._del_set_btn.clicked.connect(self._on_delete_set)

    def start_sync(self):
        self.sync_action.setEnabled(False)

        # start sync via view-model; it will create its own queue & cancel event
        self._sync_vm.start_async()

        # create and show modal progress dialog which will poll the queue and
        # instruct the view-model to cancel when the user clicks Cancel
        dlg = SyncProgressDialog(self._sync_vm, parent=self)

        # run modal dialog; it will close (switch to OK) when sync finishes
        dlg.exec()

        # re-enable action after dialog closes
        self.sync_action.setEnabled(True)
        # sync dialog handled above; nothing else needed here

    def _populate_sets_table(self, order_by: str = "set_num", descending: bool = False):
        try:
            rows = self._sets_vm.list_user_sets(order_by=order_by, descending=descending)
        except Exception:
            rows = []
        self._sets_table.blockSignals(True)
        self._sets_table.setRowCount(0)
        for r in rows:
            row = self._sets_table.rowCount()
            self._sets_table.insertRow(row)
            # Set Number editable
            item0 = QTableWidgetItem(r.get("set_num", ""))
            item0.setFlags(item0.flags() & ~Qt.ItemIsEditable)
            self._sets_table.setItem(row, 0, item0)
            # Name non-editable
            item1 = QTableWidgetItem(r.get("name", ""))
            item1.setFlags(item1.flags() & ~Qt.ItemIsEditable)
            self._sets_table.setItem(row, 1, item1)
            # Quantity editable
            item2 = QTableWidgetItem(str(r.get("quantity", 0)))
            item2.setFlags(item2.flags() | Qt.ItemIsEditable)
            self._sets_table.setItem(row, 2, item2)
            # Remark editable
            item3 = QTableWidgetItem(r.get("remark", ""))
            item3.setFlags(item3.flags() | Qt.ItemIsEditable)
            self._sets_table.setItem(row, 3, item3)
        self._sets_table.blockSignals(False)

    def _on_sets_item_changed(self, item: QTableWidgetItem):
        # persist edits to viewmodel. Determine row's set_num (may have changed)
        row = item.row()
        set_num_item = self._sets_table.item(row, 0)
        name_item = self._sets_table.item(row, 1)
        qty_item = self._sets_table.item(row, 2)
        remark_item = self._sets_table.item(row, 3)
        if not set_num_item:
            return
        set_num = set_num_item.text()
        try:
            qty = int(qty_item.text()) if qty_item and qty_item.text() != "" else 0
        except Exception:
            qty = 0
        remark = remark_item.text() if remark_item else ""
        try:
            # update or insert depending on existence
            self._sets_vm.update_user_set(set_num, qty, remark)
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", f"Set {set_num} already present")
        except Exception:
            logger.exception("Failed to update user_set %s", set_num)

    def _on_add_set(self):
        # prompt for set_num; simple flow for now
        set_num, ok = self._dialog_provider(self, "Add Set", "Set number:")
        if not ok or not set_num:
            return
        try:
            self._sets_vm.add_user_set(set_num, 1, "")
            self._populate_sets_table()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", f"Set {set_num} already present")
        except Exception:
            logger.exception("Failed to add user_set %s", set_num)

    def _on_delete_set(self):
        items = self._sets_table.selectedItems()
        if not items:
            return
        # assume first selected item's row
        row = items[0].row()
        set_num_item = self._sets_table.item(row, 0)
        if not set_num_item:
            return
        set_num = set_num_item.text()
        try:
            self._sets_vm.delete_user_set(set_num)
            self._populate_sets_table()
        except Exception:
            logger.exception("Failed to delete user_set %s", set_num)
