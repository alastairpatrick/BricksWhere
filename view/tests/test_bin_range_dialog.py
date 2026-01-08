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


def test_generate_displays_pdf(executor, app_qt):
    # provide a BinRangeViewModel with no delay so FakeExecutor won't block
    from viewmodel.bin_range_viewmodel import BinRangeViewModel

    vm = BinRangeViewModel(executor, delay=0)

    # fake PDF viewer that captures bytes
    captured = {}

    from PySide6.QtWidgets import QWidget

    class FakeViewer(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)

        def set_data(self, data):
            captured['data'] = data

    dlg = BinRangeDialog(viewmodel=vm, pdf_viewer_cls=FakeViewer)
    # enable the generate button by entering a valid range
    dlg._start.setText('A')
    dlg._end.setText('B')
    assert dlg._generate.isEnabled()

    # click generate and wait for the FakeExecutor to run the task
    dlg._generate.click()

    # process events until viewer captured data
    import time
    deadline = time.time() + 2.0
    while time.time() < deadline and 'data' not in captured:
        app_qt.processEvents()
        time.sleep(0.01)

    assert 'data' in captured
    assert isinstance(captured['data'], (bytes, bytearray))
