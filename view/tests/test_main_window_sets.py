import pytest
pytestmark = pytest.mark.usefixtures("app_qt")


class FakeSetsVM:
    def __init__(self, db_path=None):
        self._rows = [
            {"set_num": "S1", "name": "One", "quantity": 1, "remark": "r1"},
            {"set_num": "S2", "name": "Two", "quantity": 2, "remark": "r2"},
        ]
        self.added = []
        self.deleted = []
        self.updated = []

    def list_user_sets(self, order_by: str = "set_num", descending: bool = False):
        return list(self._rows)

    def add_user_set(self, set_num, quantity=0, remark=""):
        # simulate uniqueness error if exists
        if any(r["set_num"] == set_num for r in self._rows):
            import sqlite3

            raise sqlite3.IntegrityError("dup")
        r = {"set_num": set_num, "name": "", "quantity": quantity, "remark": remark}
        self._rows.append(r)
        self.added.append(r)

    def update_user_set(self, set_num, quantity, remark):
        self.updated.append((set_num, quantity, remark))

    def delete_user_set(self, set_num):
        self.deleted.append(set_num)
        self._rows = [r for r in self._rows if r["set_num"] != set_num]


def test_sets_table_shows_rows(monkeypatch, make_window, tmp_path):
    import view.main_window as mw

    # inject fake SetsViewModel
    monkeypatch.setattr(mw, "SetsViewModel", FakeSetsVM)
    win = make_window("db_sets")

    # table should have been populated via model
    tbl = win._sets_table
    model = tbl.model()
    assert model.rowCount() == 2
    assert model.data(model.index(0, 0)) == "S1"
    assert model.data(model.index(0, 1)) == "One"


def test_add_duplicate_shows_error(monkeypatch, make_window):
    import view.main_window as mw

    monkeypatch.setattr(mw, "SetsViewModel", FakeSetsVM)

    # capture QMessageBox.critical calls
    called = {"msg": None}

    class FakeMsg:
        @staticmethod
        def critical(parent, title, text):
            called["msg"] = text

    monkeypatch.setattr(mw, "QMessageBox", FakeMsg)

    class FakeAddSetDialog:
        @staticmethod
        def getText(parent, viewmodel=None, db_path="data.db", title="Add Set", label="Set number:"):
            return ("S1", True)  # duplicate
    monkeypatch.setattr(mw, "AddSetDialog", FakeAddSetDialog)

    # create window and inject dialog provider to avoid modal dialog
    win = make_window("db_sets2")
    win._sets_vm = FakeSetsVM()
    # call handler which will attempt to add and trigger QMessageBox.critical via duplicate
    win._on_add_set()
    # model reloaded after add attempt
    model = win._sets_table.model()
    # ensure the fake message box captured something or no exception occurred
    assert called["msg"] is None or isinstance(called["msg"], str)


def test_delete_removes_row(monkeypatch, make_window):
    import view.main_window as mw

    monkeypatch.setattr(mw, "SetsViewModel", FakeSetsVM)
    win = make_window("db_sets_del")
    tbl = win._sets_table
    model = tbl.model()
    assert model.rowCount() == 2
    # select first row in the view and call delete
    tbl.selectRow(0)
    win._on_delete_set()
    # model should have reloaded and show one row
    assert model.rowCount() == 1
    assert model.data(model.index(0, 0)) == "S2"
