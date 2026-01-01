from PySide6.QtWidgets import QApplication, QTreeWidgetItem, QSpinBox
from PySide6.QtCore import Qt
from view import MainWindow
from model.db import create_schema
import pytest

pytestmark = pytest.mark.usefixtures("app_qt")


def test_main_window_hides_empty_categories(tmp_path):

    db_path = str(tmp_path / "test.db")
    # create db and schema
    from model.db import create_connection, connection_ctx
    with connection_ctx(db_path) as conn, conn:
        create_schema(conn)
        cur = conn.cursor()

        # create categories alpha and beta
        cur.execute("INSERT INTO part_categories (id, name) VALUES (?,?)", (1, "Alpha"))
        cur.execute("INSERT INTO part_categories (id, name) VALUES (?,?)", (2, "Beta"))

        # insert a part only in Alpha
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("A1", "AlphaPart", 1))
        # commit handled by transactional context

    win = MainWindow(db_path)

    # apply a filter that matches Alpha only
    win._populate_parts(filter_text="Alpha")

    # collect top-level children under Parts node
    parts_children = [win._parts_node.child(i).text(0) for i in range(win._parts_node.childCount())]
    assert "Alpha" in parts_children
    assert "Beta" not in parts_children


def test_tree_selection_calls_directory_vm(make_window):
    win = make_window("db")

    # add a part item and select it
    part_item = QTreeWidgetItem(win._parts_node, ["P - Part"])
    part_item.setData(0, Qt.UserRole, "P123")
    win._tree.setCurrentItem(part_item)
    win._on_tree_selection_changed()
    assert win._directory_vm.selected_part == "P123"

    # add a set item and select it
    set_item = QTreeWidgetItem(win._sets_node, ["S - Set"])
    set_item.setData(0, Qt.UserRole + 2, "S1")
    win._tree.setCurrentItem(set_item)
    win._on_tree_selection_changed()
    assert win._directory_vm.selected_set == "S1"


def test_vm_selection_set_creates_user_fields_and_persists(make_window):
    win = make_window("db2")

    # simulate selection change to a set
    win._on_vm_selection_changed(("SET", "S1"))

    # find the nested spinbox object inside the added rows
    spinbox = None
    for i in range(win._images_layout.count()):
        w = win._images_layout.itemAt(i).widget()
        if not w:
            continue
        sb = w.findChild(QSpinBox)
        if sb:
            spinbox = sb
            break
    assert spinbox is not None
    spinbox.setValue(3)

    # MainViewModel.set_user_set should have been called
    assert win._main_vm.saved == ("S1", 3, "")


def test_start_sync_creates_dialog_and_joins(make_window):
    win = make_window("db3")

    created = {"dlg": None}

    def on_created(dlg):
        created["dlg"] = dlg

    win.dialog_created.connect(on_created)
    win.start_sync()
    # ensure dialog was emitted and exec called
    assert created["dlg"] is not None
    assert getattr(created["dlg"], "execed", True) is True
