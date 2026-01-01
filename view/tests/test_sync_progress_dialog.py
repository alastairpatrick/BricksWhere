import queue
import pytest

from PySide6.QtWidgets import QApplication
import pytest

pytestmark = pytest.mark.usefixtures("app_qt")


class FakeSyncVM:
    def __init__(self, q):
        self.progress_queue = q
        self.cancel_called = False

    def cancel(self):
        self.cancel_called = True


class FakeProgressVM:
    def __init__(self):
        self.entries = []
        self.progress = 0
        self.ready_to_close = False
        self.process_called_with = None

    def process_queue(self, q):
        self.process_called_with = q
        items = []
        try:
            while True:
                item = q.get_nowait()
                if item == "ALL_DONE":
                    self.ready_to_close = True
                    continue
                items.append(item)
        except queue.Empty:
            pass
        self.entries = items
        self.progress = min(100, len(items) * 10)


def make_dialog(monkeypatch, q):
    # inject fake progress VM into the module before creating dialog
    import view.sync_progress_dialog as mod

    monkeypatch.setattr(mod, "SyncProgressViewModel", FakeProgressVM)
    sync_vm = FakeSyncVM(q)
    from view.sync_progress_dialog import SyncProgressDialog

    dlg = SyncProgressDialog(sync_vm)
    return dlg, sync_vm, mod


def test_process_queue_updates_list_and_progress(monkeypatch):
    q = queue.Queue()
    q.put("first message")
    q.put("second message")

    dlg, sync_vm, mod = make_dialog(monkeypatch, q)

    # call processing once and verify UI updated
    dlg.process_queue_once()
    assert dlg._list.count() == 2
    assert dlg._list.item(0).text() == "first message"
    assert dlg._list.item(1).text() == "second message"
    assert dlg._progress.value() == 20
    # ensure the progress VM saw our queue
    assert dlg._progress_vm.process_called_with is sync_vm.progress_queue


def test_cancel_requests_cancel_and_appends_message(monkeypatch):
    q = queue.Queue()
    dlg, sync_vm, mod = make_dialog(monkeypatch, q)

    dlg._on_cancel()
    assert sync_vm.cancel_called is True
    # last list entry informs user cancellation requested
    assert dlg._list.count() >= 1
    assert "Cancellation requested" in dlg._list.item(dlg._list.count() - 1).text()


def test_ready_to_close_emitted_and_button_switches(monkeypatch):
    q = queue.Queue()
    q.put("ALL_DONE")
    dlg, sync_vm, mod = make_dialog(monkeypatch, q)

    emitted = {"v": False}
    dlg.ready_to_close.connect(lambda: emitted.__setitem__("v", True))
    dlg.process_queue_once()

    # after switching, cancel button becomes OK
    assert emitted["v"] is True
    assert dlg._cancel_btn.text() == "OK"
    assert dlg._progress_vm.ready_to_close is True
