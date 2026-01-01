from PySide6.QtWidgets import QLabel
import pytest

pytestmark = pytest.mark.usefixtures("app_qt")


def _row_color_text(row_widget):
    # find the QLabel that matches the color name (second label added)
    for lbl in row_widget.findChildren(QLabel):
        txt = lbl.text()
        # ignore empty labels used for image holder or totals with 'pcs'
        if txt and not txt.endswith("pcs"):
            return txt
    return ""


def test_default_sort_quantity_descending(make_window):
    win = make_window("db_sort1")

    elements = [
        {"color": "Red", "img_url": "", "count": 2, "user_count": 0, "color_id": 1},
        {"color": "Blue", "img_url": "", "count": 5, "user_count": 0, "color_id": 2},
        {"color": "Green", "img_url": "", "count": 3, "user_count": 0, "color_id": 3},
    ]

    win._main_vm.get_part_detail = lambda key: {"part_num": key, "name": "n", "elements": list(elements), "counts": {"total_pieces": 10, "total_elements": 3}}

    # render the part
    win._on_vm_selection_changed(("PART", "P1"))

    # collect the displayed color names in order
    shown = []
    for i in range(win._images_layout.count()):
        w = win._images_layout.itemAt(i).widget()
        if not w:
            continue
        shown.append(_row_color_text(w))

    assert shown == ["Blue", "Green", "Red"]


def test_sort_color_ascending(make_window):
    win = make_window("db_sort2")

    elements = [
        {"color": "Red", "img_url": "", "count": 2, "user_count": 0, "color_id": 1},
        {"color": "Blue", "img_url": "", "count": 5, "user_count": 0, "color_id": 2},
        {"color": "Green", "img_url": "", "count": 3, "user_count": 0, "color_id": 3},
    ]

    win._main_vm.get_part_detail = lambda key: {"part_num": key, "name": "n", "elements": list(elements), "counts": {"total_pieces": 10, "total_elements": 3}}

    # change sort to Color Ascending
    win._sort_key_combo.setCurrentText("Color")
    win._sort_order_combo.setCurrentText("Ascending")

    # re-render selection (apply_sort triggers get_selected path which isn't present on the fake VM)
    win._on_vm_selection_changed(("PART", "P1"))

    shown = []
    for i in range(win._images_layout.count()):
        w = win._images_layout.itemAt(i).widget()
        if not w:
            continue
        shown.append(_row_color_text(w))

    assert shown == ["Blue", "Green", "Red"]
