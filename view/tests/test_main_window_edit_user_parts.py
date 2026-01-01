import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSpinBox
from model.db import create_schema, connection_ctx

pytestmark = pytest.mark.usefixtures("app_qt")


def test_main_window_allows_editing_user_parts(monkeypatch, tmp_path):
    db_path = str(tmp_path / "ui_edit.db")
    # create DB with data
    with connection_ctx(db_path) as conn, conn:
        create_schema(conn)
        cur = conn.cursor()
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (1, "Black"))
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("P1", "Widget", None))
        cur.execute("INSERT INTO inventories (id, version, set_num) VALUES (?,?,?)", (1, 1, "S1"))
        cur.execute("INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)", (1, "P1", 1, 2, 0, ""))
        cur.execute("INSERT INTO user_sets (set_num, quantity, remark) VALUES (?,?,?)", ("S1", 1, ""))
        # pre-populate user_parts with 1 loose part
        cur.execute("INSERT INTO user_parts (part_num, color_id, quantity) VALUES (?,?,?)", ("P1", 1, 1))

    import view.main_window as mw
    import view.image_loader as imgmod
    from view.tests.conftest import FakeDirVM, FakeDialog, FakeFetcher

    monkeypatch.setattr(mw, "DirectoryViewModel", FakeDirVM)
    monkeypatch.setattr(imgmod, "BackgroundImageFetcher", FakeFetcher)
    monkeypatch.setattr(mw, "SyncProgressDialog", FakeDialog)

    win = mw.MainWindow(db_path)
    # simulate selection of part
    win._on_vm_selection_changed(("PART", "P1"))

    # find spinbox in layout
    spin = None
    for i in range(win._images_layout.count()):
        w = win._images_layout.itemAt(i).widget()
        if not w:
            continue
        sb = w.findChild(QSpinBox)
        if sb:
            spin = sb
            break
    assert spin is not None
    # initial value should be 1
    assert spin.value() == 1

    # change value to 4
    spin.setValue(4)

    # reopen details to ensure persisted
    win._on_vm_selection_changed(("PART", "P1"))
    # find updated spin value
    spin2 = None
    for i in range(win._images_layout.count()):
        w = win._images_layout.itemAt(i).widget()
        if not w:
            continue
        sb = w.findChild(QSpinBox)
        if sb:
            spin2 = sb
            break
    assert spin2 is not None
    assert spin2.value() == 4
