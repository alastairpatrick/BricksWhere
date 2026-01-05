import queue
import threading
from PySide6.QtWidgets import QApplication
from view import SyncProgressDialog
import pytest

pytestmark = pytest.mark.usefixtures("app_qt")


def test_sync_progress_dialog_processes_queue():

    # create a fake background task that exposes Qt signals like the real one
    from PySide6.QtCore import QObject, Signal

    class FakeBackgroundTask(QObject):
        progressed = Signal(str)
        completed = Signal(bool)

        def __init__(self):
            super().__init__()

        def cancel(self):
            self._cancelled = True

    class FakeVM:
        def __init__(self):
            self.background_task = FakeBackgroundTask()

    vm = FakeVM()
    dlg = SyncProgressDialog(vm)

    # emit a couple of progress messages then completion
    dlg._sync_vm.background_task.progressed.emit("Starting download")
    dlg._sync_vm.background_task.progressed.emit("Finished colors")
    dlg._sync_vm.background_task.completed.emit(True)

    # after completion, Cancel button should switch to OK
    assert dlg._cancel_btn.text() == "OK"
    dlg.close()