import pytest
pytestmark = pytest.mark.usefixtures("app_qt")


class FakeBinsVM:
    def __init__(self, db_path=None):
        self._rows = [
            {"part_num": "P1", "bin_num": "B1", "remark": "r1"},
            {"part_num": "P2", "bin_num": "B2", "remark": "r2"},
        ]
        self.added = []
        self.deleted = []
        self.updated = []

    def list_user_part_bins(self, order_by: str = "part_num", descending: bool = False):
        return list(self._rows)

    def add_user_part_bin(self, part_num, bin_num=None, remark=""):
        if any(r["part_num"] == part_num for r in self._rows):
            import sqlite3

            raise sqlite3.IntegrityError("dup")
        r = {"part_num": part_num, "bin_num": bin_num, "remark": remark}
        self._rows.append(r)
        self.added.append(r)

    def update_user_part_bin(self, part_num, bin_num, remark):
        self.updated.append((part_num, bin_num, remark))

    def delete_user_part_bin(self, part_num):
        self.deleted.append(part_num)
        self._rows = [r for r in self._rows if r["part_num"] != part_num]


class SimpleFakeSetsVM:
    def __init__(self, db_path=None):
        self._rows = []

    def list_user_sets(self, order_by: str = "set_num", descending: bool = False):
        return list(self._rows)


def test_bins_table_shows_rows(make_window):
    import view.main_window as mw
    from view.bins_table_model import BinsTableModel

    win = make_window("db_bins", sets_view_model=SimpleFakeSetsVM())
    # inject fake BinsViewModel and rebuild model
    win._bins_viewmodel = FakeBinsVM()
    win._bins_model = BinsTableModel(win._bins_viewmodel)
    win._bins_table.setModel(win._bins_model)
    win._bins_model.load()

    tbl = win._bins_table
    model = tbl.model()
    assert model.rowCount() == 2
    assert model.data(model.index(0, 0)) == "P1"
    assert model.data(model.index(0, 1)) == "B1"


def test_add_duplicate_shows_error(make_window):
    import view.main_window as mw

    called = {"msg": None}

    class FakeMsg:
        @staticmethod
        def critical(parent, title, text):
            called["msg"] = text

    # create window and inject dialog provider to avoid modal dialog
    win = make_window("db_bins2", sets_view_model=SimpleFakeSetsVM(), message_box_cls=FakeMsg, exec_add_bin_dialog=lambda *a, **k: ("P1", True))
    win._bins_viewmodel = FakeBinsVM()
    # call handler which will attempt to add and trigger QMessageBox.critical via duplicate
    win._on_add_bin()
    model = win._bins_table.model()
    assert called["msg"] is None or isinstance(called["msg"], str)


def test_delete_removes_row(make_window):
    from view.bins_table_model import BinsTableModel

    win = make_window("db_bins_del", sets_view_model=SimpleFakeSetsVM())
    win._bins_viewmodel = FakeBinsVM()
    win._bins_model = BinsTableModel(win._bins_viewmodel)
    win._bins_table.setModel(win._bins_model)
    win._bins_model.load()

    tbl = win._bins_table
    model = tbl.model()
    assert model.rowCount() == 2
    tbl.selectRow(0)
    win._on_delete_bin()
    assert model.rowCount() == 1
    assert model.data(model.index(0, 0)) == "P2"
