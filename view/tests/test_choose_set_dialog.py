import pytest
pytestmark = pytest.mark.usefixtures("app_qt")

from PySide6.QtWidgets import QDialogButtonBox

from view.choose_set_dialog import ChooseSetDialog


class FakeVM:
    def __init__(self, rows=None):
        # rows: list of (set_num, name)
        self.rows = rows or []

    def prefix_matches(self, prefix, limit=101):
        if prefix is None:
            return []
        out = [r for r in self.rows if r[0].startswith(prefix)]
        return out[:limit]

    def set_exists(self, set_num):
        return any(r[0] == set_num for r in self.rows)


def test_ok_enabled_on_exact_match():
    vm = FakeVM([("T1", "Test One")])
    dlg = ChooseSetDialog(None, viewmodel=vm)
    ok_btn = dlg._buttons.button(QDialogButtonBox.Ok)
    assert not ok_btn.isEnabled()
    dlg._edit.setText("T1")
    assert ok_btn.isEnabled()


def test_autocomplete_single_match_selects_appended():
    vm = FakeVM([("670-1", "Mobile Crane")])
    dlg = ChooseSetDialog(None, viewmodel=vm)
    dlg._edit.setText("670")
    assert dlg._edit.text() == "670-1"
    assert dlg._edit.selectedText() == "-1"


def test_results_populated_and_ellipsis_and_click():
    rows = [(f"PFX{str(i).zfill(3)}", f"Name{i}") for i in range(150)]
    vm = FakeVM(rows)
    dlg = ChooseSetDialog(None, viewmodel=vm)
    dlg._edit.setText("PFX")
    assert dlg._results.rowCount() == 101
    last_item = dlg._results.item(100, 0)
    assert last_item.text() == "..."
    first_item = dlg._results.item(0, 0)
    assert first_item.text().startswith("PFX")
    dlg._on_results_clicked(0, 0)
    ok_btn = dlg._buttons.button(QDialogButtonBox.Ok)
    assert dlg._edit.text() == first_item.text()
    assert ok_btn.isEnabled()
