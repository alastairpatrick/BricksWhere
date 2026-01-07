import logging
from PySide6.QtWidgets import QMainWindow, QTabWidget, QTableView, QPushButton, QHeaderView, QMessageBox, QVBoxLayout, QWidget, QHBoxLayout, QAbstractItemView
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal, Qt
import sqlite3

logger = logging.getLogger(__name__)

from .sync_progress_dialog import SyncProgressDialog
from viewmodel import SyncViewModel
from viewmodel.sets_viewmodel import SetsViewModel
from viewmodel.bins_viewmodel import BinsViewModel
from .bins_table_model import BinsTableModel
from .add_bin_dialog import AddBinDialog
from viewmodel.add_bin_viewmodel import AddBinViewModel


class MainWindow(QMainWindow):

    def _add_table_with_buttons(self, layout, table, add_btn, del_btn):
        """Attach `table` to `layout` and add a right-aligned add/delete button row."""
        layout.addWidget(table)
        btns = QHBoxLayout()
        btns.addStretch()
        btns.addWidget(add_btn)
        btns.addWidget(del_btn)
        layout.addLayout(btns)


    def __init__(self, db_path: str = "data.db", executor=None, requests_session=None, dialog_provider=None):
        super().__init__()
        self._db_path = db_path
        self._executor = executor
        self._requests_session = requests_session

        self._sync_vm = SyncViewModel(self._db_path, executor=self._executor)

        self.setWindowTitle("BricksWhere")

        # Menu -> Tools -> Resynchronize with Rebrickable
        tools = self.menuBar().addMenu("Tools")
        self.sync_action = QAction("Resynchronize with Rebrickable", self)
        self.sync_action.triggered.connect(self.start_sync)
        tools.addAction(self.sync_action)

        # Menu -> Reports -> Bin Range
        reports = self.menuBar().addMenu("Reports")
        self.report_bin_action = QAction("Bin Range", self)
        self.report_bin_action.triggered.connect(self._on_report_bin_range)
        reports.addAction(self.report_bin_action)

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
        # add table and standard right-aligned Add/Delete buttons
        self._add_set_btn = QPushButton("Add")
        self._del_set_btn = QPushButton("Delete")
        self._add_table_with_buttons(sets_layout, self._sets_table, self._add_set_btn, self._del_set_btn)

        # Placeholder tab
        self._placeholder_tab = QWidget()

        self._tab_widget.addTab(self._sets_tab, "Sets")
        self._tab_widget.addTab(self._placeholder_tab, "Placeholder")

        # Bins tab
        self._bins_tab = QWidget()
        bins_layout = QVBoxLayout(self._bins_tab)
        self._bins_viewmodel = BinsViewModel(self._db_path)
        self._bins_model = BinsTableModel(self._bins_viewmodel)
        self._bins_table = QTableView(self)
        self._bins_table.setModel(self._bins_model)
        self._bins_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._bins_table.setSortingEnabled(True)
        self._bins_model.load()
        add_bin_btn = QPushButton("Add")
        del_bin_btn = QPushButton("Delete")
        self._add_table_with_buttons(bins_layout, self._bins_table, add_bin_btn, del_bin_btn)
        add_bin_btn.clicked.connect(self._on_add_bin)
        del_bin_btn.clicked.connect(self._on_delete_bin)
        self._tab_widget.addTab(self._bins_tab, "Bins")

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

    # Table is backed by `SetsTableModel` which persists edits via the viewmodel.

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

    def _on_add_bin(self):
        add_vm = AddBinViewModel(self._db_path)
        part = AddBinDialog.getText(add_vm, self)
        if not part:
            return
        try:
            self._bins_viewmodel.add_user_part_bin(part, None, "")
            self._bins_model.load()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", f"Part {part} already present in bins")
        except Exception:
            logger.exception("Failed to add user_part_bin %s", part)

    def _on_report_bin_range(self):
        # show the bin range dialog; dialog currently does nothing on Generate
        try:
            # allow tests to monkeypatch `BinRangeDialog` on this module by
            # preferring a module-level name if present; otherwise import
            dlg_cls = globals().get("BinRangeDialog")
            if dlg_cls is None:
                from .bin_range_dialog import BinRangeDialog as dlg_cls

            dlg = dlg_cls(self, executor=self._executor)
            dlg.exec()
        except Exception:
            logger.exception("Failed showing Bin Range dialog")

    def _on_delete_bin(self):
        sel = self._bins_table.selectionModel().selectedRows()
        if not sel:
            return
        row = sel[0].row()
        model = self._bins_table.model()
        part_num = model.data(model.index(row, 0))
        if not part_num:
            return
        try:
            self._bins_viewmodel.delete_user_part_bin(part_num)
            self._bins_model.load()
        except Exception:
            logger.exception("Failed to delete user_part_bin %s", part_num)
