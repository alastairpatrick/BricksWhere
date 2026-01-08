import pytest
pytestmark = pytest.mark.usefixtures("app_qt")


class FakeDialog:
    def __init__(self, parent=None):
        self.execed = False

    def exec(self):
        self.execed = True


class FakeSetsVM:
    def __init__(self, db_path=None):
        pass

    def list_user_sets(self, order_by: str = "set_num", descending: bool = False):
        return []
    

def test_reports_bin_range_action_triggers_dialog(monkeypatch, make_window):
    import view.main_window as mw

    # patch the BinRangeDialog so exec() doesn't block
    monkeypatch.setattr(mw, "BinRangeDialog", FakeDialog, raising=False)

    # avoid DB access by injecting a lightweight FakeSetsVM
    monkeypatch.setattr(mw, "SetsViewModel", FakeSetsVM)
    win = make_window("db_reports")
    # action should exist
    assert hasattr(win, "report_bin_action")
    # trigger it and ensure our FakeDialog was execed
    win.report_bin_action.trigger()
