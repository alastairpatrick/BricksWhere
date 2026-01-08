import pytest
from PySide6.QtWidgets import QApplication
from view.main_window import MainWindow

class FakeDialog:
    def __init__(self, sync_vm, parent=None):
        self.sync_vm = sync_vm
        self.execed = False

    def exec(self):
        self.execed = True


@pytest.fixture
def make_window(tmp_path):
    def _make(name="db", **kwargs):
        return MainWindow(str(tmp_path / name), sync_progress_dialog_cls=FakeDialog, **kwargs)

    return _make
