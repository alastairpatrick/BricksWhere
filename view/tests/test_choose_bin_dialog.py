import pytest
pytestmark = pytest.mark.usefixtures("app_qt")

from PySide6.QtWidgets import QDialogButtonBox

from view.choose_bin_dialog import ChooseBinDialog


class FakeVM:
    def __init__(self, rows=None):
        # rows: list of (part_num, name)
        self.rows = rows or []

    def prefix_matches(self, prefix, limit=101):
        if prefix is None:
            return []
        out = [r for r in self.rows if r[0].startswith(prefix)]
        return out[:limit]

    def part_exists(self, part_num):
        return any(r[0] == part_num for r in self.rows)


def test_ok_enabled_on_exact_match():
    vm = FakeVM([("P1", "Part One")])
    dlg = ChooseBinDialog(viewmodel=vm)
    ok_btn = dlg.ok
    assert not ok_btn.isEnabled()
    dlg.input.setText("P1")
    assert ok_btn.isEnabled()


def test_autocomplete_single_match_selects_appended():
    vm = FakeVM([("ABC-1", "Thing")])
    dlg = ChooseBinDialog(viewmodel=vm)
    dlg.input.setText("ABC")
    assert dlg.input.text().startswith("ABC")


def test_results_populated_and_ellipsis_and_click():
    rows = [(f"PFX{str(i).zfill(3)}", f"Name{i}") for i in range(150)]
    vm = FakeVM(rows)
    dlg = ChooseBinDialog(viewmodel=vm)
    dlg.input.setText("PFX")
    assert dlg.results.rowCount() == 101
    last_item = dlg.results.item(100, 0)
    assert last_item.text() == "..."
    first_item = dlg.results.item(0, 0)
    assert first_item.text().startswith("PFX")
    dlg._on_result_click(0, 0)
    assert dlg.input.text() == first_item.text()
    assert dlg.ok.isEnabled()
