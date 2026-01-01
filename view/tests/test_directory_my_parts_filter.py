import pytest
from model.db import create_schema, connection_ctx
from PySide6.QtWidgets import QTreeWidgetItem

pytestmark = pytest.mark.usefixtures("app_qt")


def test_my_parts_checkbox_filters_categories_and_sets(tmp_path):
    db_path = str(tmp_path / "filter.db")
    with connection_ctx(db_path) as conn, conn:
        create_schema(conn)
        cur = conn.cursor()
        # create categories
        cur.execute("INSERT INTO part_categories (id, name) VALUES (?,?)", (1, "Alpha"))
        cur.execute("INSERT INTO part_categories (id, name) VALUES (?,?)", (2, "Beta"))
        # create parts in categories
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("A1", "AlphaPart", 1))
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("B1", "BetaPart", 2))
        # mark A1 as owned via user_parts
        cur.execute("INSERT INTO user_parts (part_num, color_id, quantity) VALUES (?,?,?)", ("A1", 1, 2))

        # create themes and sets
        cur.execute("INSERT INTO themes (id, name, parent_id) VALUES (?,?,?)", (1, "Theme1", None))
        cur.execute("INSERT INTO themes (id, name, parent_id) VALUES (?,?,?)", (2, "Theme2", None))
        cur.execute("INSERT INTO sets (set_num, name, year, theme_id, num_parts, img_url) VALUES (?,?,?,?,?,?)", ("S1", "SetOne", 2020, 1, 10, ""))
        cur.execute("INSERT INTO sets (set_num, name, year, theme_id, num_parts, img_url) VALUES (?,?,?,?,?,?)", ("S2", "SetTwo", 2021, 2, 8, ""))
        # user owns S1 only
        cur.execute("INSERT INTO user_sets (set_num, quantity, remark) VALUES (?,?,?)", ("S1", 1, ""))

    # create main window with real DirectoryViewModel
    import view.main_window as mw

    win = mw.MainWindow(db_path)

    # initial state: checkbox unchecked -> both categories should be present
    win._only_my_checkbox.setChecked(False)
    win._populate_parts(filter_text="")
    parts_children = [win._parts_node.child(i).text(0) for i in range(win._parts_node.childCount())]
    assert "Alpha" in parts_children
    assert "Beta" in parts_children

    # check box checked: only Alpha (because A1 owned) should be present
    win._only_my_checkbox.setChecked(True)
    win._populate_parts(filter_text="")
    parts_children = [win._parts_node.child(i).text(0) for i in range(win._parts_node.childCount())]
    assert "Alpha" in parts_children
    assert "Beta" not in parts_children

    # themes/sets: when unchecked both themes present
    win._only_my_checkbox.setChecked(False)
    win._populate_parts(filter_text="")
    sets_children = [win._sets_node.child(i).text(0) for i in range(win._sets_node.childCount())]
    assert "Theme1" in sets_children
    assert "Theme2" in sets_children

    # when checked only Theme1 (has S1 owned) should be present
    win._only_my_checkbox.setChecked(True)
    win._populate_parts(filter_text="")
    sets_children = [win._sets_node.child(i).text(0) for i in range(win._sets_node.childCount())]
    assert "Theme1" in sets_children
    assert "Theme2" not in sets_children
