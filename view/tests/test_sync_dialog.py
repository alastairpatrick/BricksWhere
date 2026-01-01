import queue
import threading
from PySide6.QtWidgets import QApplication
from view import SyncProgressDialog
import pytest

pytestmark = pytest.mark.usefixtures("app_qt")


def test_sync_progress_dialog_processes_queue():

    q = queue.Queue()
    q.put("Starting download")
    q.put("Finished colors")
    q.put("ALL_DONE")

    # create a SyncViewModel and attach the prepared queue so the dialog can use it
    from viewmodel import SyncViewModel
    vm = SyncViewModel()
    vm._progress_q = q

    dlg = SyncProgressDialog(vm)

    called = {"ready": False}

    def on_ready():
        called["ready"] = True

    try:
        dlg.ready_to_close.connect(on_ready)
        # process queue synchronously
        dlg.process_queue_once()
        # after processing, Cancel button should be switched to OK
        assert dlg._cancel_btn.text() == "OK"
        assert called["ready"] is True
    finally:
        dlg.close()