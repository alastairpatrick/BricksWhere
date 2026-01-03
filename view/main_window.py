import logging
from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal

logger = logging.getLogger(__name__)

from .sync_progress_dialog import SyncProgressDialog
from viewmodel import SyncViewModel


class MainWindow(QMainWindow):
    # emitted when a sync dialog is created; test hook for deterministic tests
    dialog_created = Signal(object)

    def __init__(self, db_path: str = "data.db"):
        super().__init__()
        self.setWindowTitle("BricksWhere")
        self._db_path = db_path

        # Menu -> Tools -> Resynchronize with Rebrickable
        tools = self.menuBar().addMenu("Tools")
        self.sync_action = QAction("Resynchronize with Rebrickable", self)
        self.sync_action.triggered.connect(self.start_sync)
        tools.addAction(self.sync_action)

        self._sync_vm = SyncViewModel(self._db_path)

    def start_sync(self):
        self.sync_action.setEnabled(False)

        # start sync via view-model; it will create its own queue & cancel event
        self._sync_vm.start_async()

        # create and show modal progress dialog which will poll the queue and
        # instruct the view-model to cancel when the user clicks Cancel
        dlg = SyncProgressDialog(self._sync_vm, parent=self)
        # notify listeners/tests that the dialog was created
        self.dialog_created.emit(dlg)

        # run modal dialog; it will close (switch to OK) when sync finishes
        dlg.exec()

        # ensure sync thread is finished before refreshing UI
        self._sync_vm.join()

        # re-enable action after dialog closes
        self.sync_action.setEnabled(True)
