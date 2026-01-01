import queue
import pytest
from PySide6.QtWidgets import QApplication


class FakeDirVM:
    def __init__(self, db_path, on_search_applied=None, on_selection_changed=None):
        self.db_path = db_path
        self.on_search_applied = on_search_applied
        self.on_selection_changed = on_selection_changed
        self.selected_part = None
        self.selected_set = None

    def get_categories(self, filter_text="", only_my: bool = False):
        return []

    def get_themes(self, filter_text="", only_my: bool = False):
        return []

    def list_parts(self, expanded, filter_text="", only_my: bool = False):
        return {}, False, {}

    def list_sets(self, expanded, filter_text="", only_my: bool = False):
        return {}, False, {}

    def select_part(self, part_num):
        self.selected_part = part_num

    def select_set(self, set_num):
        self.selected_set = set_num


class FakeMainVM:
    def __init__(self, db_path=None):
        self.saved = None

    def get_set_detail(self, set_num):
        return {"set_num": set_num, "name": "SetName", "img_url": "http://example.com/img.jpg"}

    def get_user_set(self, set_num):
        return {"set_num": set_num, "quantity": 0, "remark": ""}

    def set_user_set(self, set_num, quantity, remark):
        self.saved = (set_num, quantity, remark)

    def get_part_detail(self, part_num):
        return {"part_num": part_num, "name": "PartName", "colors": [], "elements": []}


class FakeSyncVM:
    def __init__(self, db_path=None):
        self.started = False

    def start_async(self):
        self.started = True
        return queue.Queue()

    def join(self):
        return

    def cancel(self):
        self.cancelled = True


class FakeFetcher:
    def __init__(self, db_path):
        self.db_path = db_path
        self.started_with = None

    def start(self, elements):
        import queue as _q

        self.started_with = list(elements)
        q = _q.Queue()
        q.put(("color", b"data"))
        q.put("ALL_DONE")
        return q

    def cancel(self):
        pass

    def join(self):
        pass


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
    import view.image_loader as imgmod

    monkeypatch.setattr(mw, "DirectoryViewModel", FakeDirVM)
    monkeypatch.setattr(mw, "MainViewModel", FakeMainVM)
    monkeypatch.setattr(mw, "SyncViewModel", FakeSyncVM)
    monkeypatch.setattr(imgmod, "BackgroundImageFetcher", FakeFetcher)
    # patch dialog to avoid modal exec
    monkeypatch.setattr(mw, "SyncProgressDialog", FakeDialog)
    return mw


@pytest.fixture
def make_window(patched_mw, tmp_path):
    def _make(name="db"):
        return patched_mw.MainWindow(str(tmp_path / name))

    return _make
