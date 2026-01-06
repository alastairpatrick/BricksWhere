import pytest
pytestmark = [pytest.mark.usefixtures("app_qt"), pytest.mark.schema]

import sqlite3

from view.add_set_dialog import AddSetDialog
from PySide6.QtWidgets import QDialogButtonBox


def test_ok_enabled_on_exact_match(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    cur.execute("INSERT INTO sets (set_num, name) VALUES (?,?)", ("T1", "Test One"))
    conn.commit()
    conn.close()

    dlg = AddSetDialog(None, db_path=db)
    # initially OK disabled
    ok_btn = dlg._buttons.button(QDialogButtonBox.Ok)
    assert not ok_btn.isEnabled()

    # type exact set number
    dlg._edit.setText("T1")
    assert ok_btn.isEnabled()


def test_autocomplete_single_match_selects_appended(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    cur.execute("INSERT INTO sets (set_num, name) VALUES (?,?)", ("670-1", "Mobile Crane"))
    conn.commit()
    conn.close()

    dlg = AddSetDialog(None, db_path=db)
    dlg._edit.setText("670")
    # should have autocompleted
    assert dlg._edit.text() == "670-1"
    # appended part should be selected
    assert dlg._edit.selectedText() == "-1"


def test_results_populated_and_ellipsis_and_click(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    # insert 150 sets with prefix PFX
    rows = [(f"PFX{str(i).zfill(3)}", f"Name{i}") for i in range(150)]
    cur.executemany("INSERT INTO sets (set_num, name) VALUES (?,?)", rows)
    conn.commit()
    conn.close()

    dlg = AddSetDialog(None, db_path=db)
    dlg._edit.setText("PFX")
    # view should show 100 rows plus ellipsis => 101
    assert dlg._results.rowCount() == 101
    last_item = dlg._results.item(100, 0)
    assert last_item.text() == "..."

    # click first real row and ensure edit filled and OK enabled
    first_item = dlg._results.item(0, 0)
    assert first_item.text().startswith("PFX")
    dlg._on_results_clicked(0, 0)
    ok_btn = dlg._buttons.button(QDialogButtonBox.Ok)
    assert dlg._edit.text() == first_item.text()
    assert ok_btn.isEnabled()
