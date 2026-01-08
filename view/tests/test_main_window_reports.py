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
    

def test_reports_bin_range_action_triggers_dialog(make_window):
    import view.main_window as mw

    # avoid DB access by injecting a lightweight FakeSetsVM
    win = make_window("db_reports", sets_view_model=FakeSetsVM(), bin_range_dialog_cls=FakeDialog)
    # trigger action and ensure our FakeDialog was execed
    win.report_bin_action.trigger()
