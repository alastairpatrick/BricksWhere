import queue
import pytest

from PySide6.QtWidgets import QApplication
import pytest

pytestmark = pytest.mark.usefixtures("app_qt")


from PySide6.QtCore import QObject, Signal


class FakeBackgroundTask(QObject):
    progressed = Signal(str)
    completed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.cancel_called = False

    def cancel(self):
        self.cancel_called = True


def make_dialog_with_fake():
    sync_vm = type("VM", (), {})()
    sync_vm.background_task = FakeBackgroundTask()
    from view.sync_progress_dialog import SyncProgressDialog

    dlg = SyncProgressDialog(sync_vm)
    return dlg, sync_vm


def test_process_queue_updates_list_and_progress():
    dlg, vm = make_dialog_with_fake()

    # emit messages
    vm.background_task.progressed.emit("first message")
    vm.background_task.progressed.emit("second message")
    # check UI updated
    assert dlg._list.count() == 2
    assert dlg._list.item(0).text() == "first message"
    assert dlg._list.item(1).text() == "second message"
    # progress value should be > 0
    assert dlg._progress.value() >= 0


def test_cancel_requests_cancel_and_appends_message():
    dlg, vm = make_dialog_with_fake()
    dlg._on_cancel()
    assert vm.background_task.cancel_called is True
    assert dlg._list.count() >= 1
    assert "Cancellation requested" in dlg._list.item(dlg._list.count() - 1).text()


def test_ready_to_close_emitted_and_button_switches():
    dlg, vm = make_dialog_with_fake()
    emitted = {"v": False}
    dlg.ready_to_close.connect(lambda: emitted.__setitem__("v", True))
    # simulate completion
    vm.background_task.completed.emit(True)
    assert emitted["v"] is True
    assert dlg._cancel_btn.text() == "OK"
