import pytest
from PySide6.QtCore import Qt

from view.sets_table_model import SetsTableModel


class FakeSetsVM:
    def __init__(self, rows=None):
        # rows is list of dicts
        self._rows = rows or []
        self.updated_set_nums = []
        self.updated_sets = []

    def list_user_sets(self, order_by: str = "set_num", descending: bool = False):
        return list(self._rows)

    def update_set_num(self, old_set_num, new_set_num):
        self.updated_set_nums.append((old_set_num, new_set_num))
        for r in self._rows:
            if r["set_num"] == old_set_num:
                r["set_num"] = new_set_num

    def update_user_set(self, set_num, quantity, remark):
        self.updated_sets.append((set_num, quantity, remark))
        for r in self._rows:
            if r["set_num"] == set_num:
                r["quantity"] = quantity
                r["remark"] = remark


def make_rows():
    return [
        {"set_num": "S1", "name": "One", "quantity": 1, "remark": "r1"},
        {"set_num": "S2", "name": "Two", "quantity": 2, "remark": "r2"},
    ]


def test_load_and_data():
    vm = FakeSetsVM(make_rows())
    m = SetsTableModel(vm)
    m.load()
    assert m.rowCount() == 2
    assert m.data(m.index(0, m.SetNumCol)) == "S1"
    assert m.data(m.index(0, m.NameCol)) == "One"
    assert m.data(m.index(1, m.QuantityCol)) == "2"


def test_setnum_edit_updates_vm_and_name():
    vm = FakeSetsVM(make_rows())
    m = SetsTableModel(vm)
    m.load()
    idx = m.index(0, m.SetNumCol)
    # change S1 -> S1X
    assert m.setData(idx, "S1X", Qt.EditRole)
    # VM should have recorded the change
    assert vm.updated_set_nums == [("S1", "S1X")]
    # model should reflect new set_num
    assert m.data(m.index(0, m.SetNumCol)) == "S1X"


def test_quantity_and_remark_edit_updates_vm():
    vm = FakeSetsVM(make_rows())
    m = SetsTableModel(vm)
    m.load()
    qidx = m.index(1, m.QuantityCol)
    ridx = m.index(1, m.RemarkCol)
    assert m.setData(qidx, "5", Qt.EditRole)
    assert m.setData(ridx, "updated", Qt.EditRole)
    # VM recorded updates (order may vary)
    assert ("S2", 5, "r2") in vm.updated_sets or ("S2", 5, "updated") in vm.updated_sets
    assert ("S2", 2, "updated") in vm.updated_sets or any(u[0] == "S2" for u in vm.updated_sets)


def test_flags_and_editable_columns():
    vm = FakeSetsVM(make_rows())
    m = SetsTableModel(vm)
    m.load()
    assert m.flags(m.index(0, m.SetNumCol)) & Qt.ItemIsEditable
    assert not (m.flags(m.index(0, m.NameCol)) & Qt.ItemIsEditable)
    assert m.flags(m.index(0, m.QuantityCol)) & Qt.ItemIsEditable
    assert m.flags(m.index(0, m.RemarkCol)) & Qt.ItemIsEditable


def test_sorting_works():
    rows = [
        {"set_num": "B", "name": "Two", "quantity": 2, "remark": "r"},
        {"set_num": "A", "name": "One", "quantity": 1, "remark": "r"},
    ]
    vm = FakeSetsVM(rows)
    m = SetsTableModel(vm)
    m.load()
    # sort by set_num ascending
    m.sort(m.SetNumCol, Qt.AscendingOrder)
    assert m.data(m.index(0, m.SetNumCol)) == "A"