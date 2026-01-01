import os
from model.db import create_connection, create_schema, connection_ctx
from viewmodel import MainViewModel


def make_png(path):
    # create a minimal 1x1 PNG binary
    data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with open(path, "wb") as f:
        f.write(data)


def test_get_part_detail_with_images(tmp_path):
    db_path = str(tmp_path / "test.db")
    with connection_ctx(db_path) as conn, conn:
        create_schema(conn)
        cur = conn.cursor()
        # create color, part, inventory_parts
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (1, "Black"))
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (2, "Blue"))
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("P1", "Widget", None))
        # create local image files
        img1 = tmp_path / "img1.png"
        img2 = tmp_path / "img2.png"
        make_png(str(img1))
        make_png(str(img2))
        cur.execute("INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)", (1, "P1", 1, 1, 0, str(img1)))
        # duplicate entry for color 1 should be ignored by the viewmodel (display once)
        cur.execute("INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)", (2, "P1", 1, 1, 0, str(img1)))
        cur.execute("INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)", (1, "P1", 2, 1, 0, str(img2)))
        # commit handled by `with conn:` transaction context

    vm = MainViewModel(db_path)
    info = vm.get_part_detail("P1")
    assert info["part_num"] == "P1"
    assert any(e["color"] == "Black" for e in info["elements"])
    assert any(e["color"] == "Blue" for e in info["elements"])
    # ensure duplicate inventory_parts rows don't cause duplicate colors
    colors = [e["color"] for e in info["elements"]]
    assert colors.count("Black") == 1
    # image paths preserved
    assert any(os.path.exists(e["img_url"]) for e in info["elements"]) is True
