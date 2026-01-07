import pytest
pytestmark = pytest.mark.usefixtures("app_qt")

from PySide6.QtWidgets import QDialog

from view.bin_range_dialog import BinRangeDialog


def test_generate_disabled_until_valid_range():
    dlg = BinRangeDialog()
    gen = dlg._generate
    assert not gen.isEnabled()
    # partial input keeps it disabled
    dlg._start.setText("B")
    assert not gen.isEnabled()
    dlg._end.setText("A")
    # end sorts before start -> disabled
    assert not gen.isEnabled()
    dlg._end.setText("C")
    # end sorts after start -> enabled
    assert gen.isEnabled()


def test_include_images_unchecked_by_default_and_cancel_closes():
    dlg = BinRangeDialog()
    assert dlg.include_images is False
    # clicking cancel should reject the dialog
    dlg._cancel.click()
    assert dlg.result() == QDialog.Rejected
