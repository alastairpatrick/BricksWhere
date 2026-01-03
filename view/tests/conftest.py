import pytest
from PySide6.QtWidgets import QApplication

class FakeDialog:
    def __init__(self, sync_vm, parent=None):
        self.sync_vm = sync_vm
        self.execed = False

    def exec(self):
        self.execed = True


@pytest.fixture(scope="session")
def app_qt():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def patched_mw(monkeypatch):
    import view.main_window as mw
    # patch dialog to avoid modal exec
    monkeypatch.setattr(mw, "SyncProgressDialog", FakeDialog)
    return mw


@pytest.fixture
def make_window(patched_mw, tmp_path):
    def _make(name="db"):
        return patched_mw.MainWindow(str(tmp_path / name))

    return _make
