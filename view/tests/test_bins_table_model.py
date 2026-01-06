import pytest
from PySide6.QtCore import Qt

from view.bins_table_model import BinsTableModel


class FakeBinsVM:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.updated_parts = []

    def list_user_part_bins(self, order_by: str = "part_num", descending: bool = False):
        return list(self._rows)

    def update_part_num(self, old, new):
        self.updated_parts.append((old, new))
        for r in self._rows:
            if r["part_num"] == old:
                r["part_num"] = new

    def update_user_part_bin(self, part_num, bin_num, remark):
        self.updated_parts.append((part_num, bin_num, remark))
        for r in self._rows:
            if r["part_num"] == part_num:
                r["bin_num"] = bin_num
                r["remark"] = remark


def make_rows():
    return [
        {"part_num": "P1", "bin_num": "A1", "remark": "r1"},
        {"part_num": "P2", "bin_num": "B2", "remark": "r2"},
    ]


def test_load_and_data():
    vm = FakeBinsVM(make_rows())
    m = BinsTableModel(vm)
    m.load()
    assert m.rowCount() == 2
    assert m.data(m.index(0, m.PartNumCol)) == "P1"
    assert m.data(m.index(0, m.BinNumCol)) == "A1"


def test_partnum_edit_updates_vm():
    vm = FakeBinsVM(make_rows())
    m = BinsTableModel(vm)
    m.load()
    idx = m.index(0, m.PartNumCol)
    assert m.setData(idx, "P1X", Qt.EditRole)
    assert vm.updated_parts == [("P1", "P1X")]
    assert m.data(m.index(0, m.PartNumCol)) == "P1X"


def test_bin_and_remark_edit_updates_vm():
    vm = FakeBinsVM(make_rows())
    m = BinsTableModel(vm)
    m.load()
    bidx = m.index(1, m.BinNumCol)
    ridx = m.index(1, m.RemarkCol)
    assert m.setData(bidx, "Z9", Qt.EditRole)
    assert m.setData(ridx, "updated", Qt.EditRole)
    assert any(u[0] == "P2" for u in vm.updated_parts)
