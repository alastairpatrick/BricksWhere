from concurrent.futures import ThreadPoolExecutor
import logging
from PySide6.QtWidgets import QMainWindow, QTabWidget, QTableView, QPushButton, QHeaderView, QMessageBox, QVBoxLayout, QWidget, QHBoxLayout, QAbstractItemView
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
        # use QTableView with a QAbstractTableModel for performance and testability
        self._sets_table = QTableView()
        # select whole rows when clicked to make delete behavior intuitive
        self._sets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._sets_table.setSelectionMode(QAbstractItemView.SingleSelection)
        # model provided below
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

        # table model
        from .sets_table_model import SetsTableModel
        self._sets_model = SetsTableModel(self._sets_vm)
        self._sets_table.setModel(self._sets_model)
        self._sets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._sets_table.setSortingEnabled(True)
        # load initial data
        self._sets_model.load()

        # dialog provider is a callable(parent, title, label) -> (text, ok)
        if dialog_provider is None:
            def _default_dialog_provider(parent, title, label):
                # use AddSetDialog which validates existence in the sets table
                from .add_set_dialog import AddSetDialog

                return AddSetDialog.getText(parent, None, self._db_path, title, label)

            self._dialog_provider = _default_dialog_provider
        else:
            self._dialog_provider = dialog_provider

        # wire up sets table handlers
        # editing is handled by the model which persists via the SetsViewModel
        # provide add/delete button handlers that operate via the viewmodel and reload model
        self._add_set_btn.clicked.connect(self._on_add_set)
        self._del_set_btn.clicked.connect(self._on_delete_set)
        # Note: previously we used itemChanged; model persists changes automatically

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

    # NOTE: Table is now backed by SetsTableModel which persists edits via the viewmodel.

    def _on_add_set(self):
        # prompt for set_num; simple flow for now
        set_num, ok = self._dialog_provider(self, "Add Set", "Set number:")
        if not ok or not set_num:
            return
        try:
            self._sets_vm.add_user_set(set_num, 1, "")
            self._sets_model.load()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", f"Set {set_num} already present")
        except Exception:
            logger.exception("Failed to add user_set %s", set_num)

    def _on_delete_set(self):
        sel = self._sets_table.selectionModel().selectedRows()
        if not sel:
            return
        row = sel[0].row()
        model = self._sets_table.model()
        set_num = model.data(model.index(row, 0))
        if not set_num:
            return
        try:
            self._sets_vm.delete_user_set(set_num)
            self._sets_model.load()
        except Exception:
            logger.exception("Failed to delete user_set %s", set_num)
