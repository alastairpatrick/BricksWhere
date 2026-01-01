import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from model.db import create_schema, connection_ctx
from view.tests.conftest import FakeFetcher, FakeDialog, FakeDirVM

pytestmark = pytest.mark.usefixtures("app_qt")


def test_main_window_shows_counts(monkeypatch, tmp_path):
    db_path = str(tmp_path / "ui_counts.db")
    # create DB with data
    with connection_ctx(db_path) as conn, conn:
        create_schema(conn)
        cur = conn.cursor()
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (1, "Black"))
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (2, "Blue"))
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("P1", "Widget", None))
        cur.execute("INSERT INTO inventories (id, version, set_num) VALUES (?,?,?)", (1, 1, "S1"))
        cur.execute("INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)", (1, "P1", 1, 2, 0, ""))
        cur.execute("INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)", (1, "P1", 2, 3, 0, ""))
        cur.execute("INSERT INTO user_sets (set_num, quantity, remark) VALUES (?,?,?)", ("S1", 2, ""))

    # patch DirectoryViewModel and image fetcher/dialog but keep real MainViewModel
    import view.main_window as mw
    import view.image_loader as imgmod

    monkeypatch.setattr(mw, "DirectoryViewModel", FakeDirVM)
    monkeypatch.setattr(imgmod, "BackgroundImageFetcher", FakeFetcher)
    monkeypatch.setattr(mw, "SyncProgressDialog", FakeDialog)

    win = mw.MainWindow(db_path)
    # simulate selection of part
    win._on_vm_selection_changed(("PART", "P1"))

    # check detail text contains totals (2*2 + 3*2 = 10 pieces across 2 elements)
    detail = win._detail.toPlainText()
    assert "Collection:" in detail
    assert "10 piece(s)" in detail
    assert "2 element(s)" in detail

    # find count labels in images layout
    found_counts = []
    for i in range(win._images_layout.count()):
        w = win._images_layout.itemAt(i).widget()
        if not w:
            continue
        # find QLabel children inside this row
        labels = w.findChildren(QLabel)
        for lbl in labels:
            txt = lbl.text()
            if txt.endswith("pcs"):
                found_counts.append(txt)

    # expecting color counts "4 pcs" and "6 pcs" (Black:2*2=4, Blue:3*2=6)
    assert "4 pcs" in found_counts
    assert "6 pcs" in found_counts
