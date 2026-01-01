import os
from model.db import connection_ctx, create_schema
from viewmodel.main_viewmodel import MainViewModel

import pytest

@pytest.mark.schema
def test_main_viewmodel_get_part_detail(sqlite_db):
    db, conn = sqlite_db

    # insert color, part, element
    cur = conn.cursor()
    cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (1, "Black"))
    cur.execute("INSERT INTO parts (part_num, name) VALUES (?,?)", ("P1", "Widget"))
    cur.execute("INSERT INTO elements (element_id, part_num, color_id) VALUES (?,?,?)", ("E1", "P1", 1))
    conn.commit()

    vm = MainViewModel(str(db))
    info = vm.get_part_detail("P1")
    assert info["part_num"] == "P1"
    assert info["name"] == "Widget"
    assert info["colors"] == ["Black"]


@pytest.mark.schema
def test_main_viewmodel_get_set_detail(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    cur.execute("INSERT INTO sets (set_num, name, img_url) VALUES (?,?,?)", ("6001-1", "Sample Set", "file:///does/not/exist.png"))
    conn.commit()

    vm = MainViewModel(str(db))
    info = vm.get_set_detail("6001-1")
    assert info["set_num"] == "6001-1"
    assert info["name"] == "Sample Set"
    assert info["img_url"] == "file:///does/not/exist.png"


@pytest.mark.schema
def test_main_viewmodel_user_set_upsert(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    # ensure set exists
    cur.execute("INSERT INTO sets (set_num, name) VALUES (?,?)", ("7000-1", "MySet"))
    conn.commit()

    vm = MainViewModel(str(db))
    # default when not present
    user = vm.get_user_set("7000-1")
    assert user["quantity"] == 0
    assert user["remark"] == ""

    # upsert create
    vm.set_user_set("7000-1", 3, "Stored")
    user2 = vm.get_user_set("7000-1")
    assert user2["quantity"] == 3
    assert user2["remark"] == "Stored"

    # update
    vm.set_user_set("7000-1", 5, "Changed")
    user3 = vm.get_user_set("7000-1")
    assert user3["quantity"] == 5
    assert user3["remark"] == "Changed"


def test_get_part_detail_counts(tmp_path):
    db_path = str(tmp_path / "counts.db")
    with connection_ctx(db_path) as conn, conn:
        create_schema(conn)
        cur = conn.cursor()
        # colors
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (1, "Black"))
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (2, "Blue"))
        # part
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("P1", "Widget", None))
        # inventories corresponding to sets S1 and S2
        cur.execute("INSERT INTO inventories (id, version, set_num) VALUES (?,?,?)", (1, 1, "S1"))
        cur.execute("INSERT INTO inventories (id, version, set_num) VALUES (?,?,?)", (2, 1, "S2"))
        # inventory_parts: inventory 1 has color1 qty=2 and color2 qty=3; inventory2 has color1 qty=1
        cur.execute(
            "INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)",
            (1, "P1", 1, 2, 0, ""),
        )
        cur.execute(
            "INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)",
            (1, "P1", 2, 3, 0, ""),
        )
        cur.execute(
            "INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)",
            (2, "P1", 1, 1, 0, ""),
        )
        # user owns 2 of S1 and 1 of S2
        cur.execute("INSERT INTO user_sets (set_num, quantity, remark) VALUES (?,?,?)", ("S1", 2, ""))
        cur.execute("INSERT INTO user_sets (set_num, quantity, remark) VALUES (?,?,?)", ("S2", 1, ""))

    vm = MainViewModel(db_path)
    info = vm.get_part_detail("P1")
    # ensure counts structure present
    assert "counts" in info
    counts = info["counts"]
    # per-color expected: color 1 -> (2*2)+(1*1)=5, color2 -> (3*2)=6
    per_color = counts["per_color"]
    assert per_color.get(1) == 5
    assert per_color.get(2) == 6
    # totals
    assert counts["total_pieces"] == 11
    assert counts["total_elements"] == 2
    # element entries should include 'count' fields matching per_color
    el_map = {e["color"]: e for e in info["elements"]}
    assert int(el_map["Black"]["count"]) == 5
    assert int(el_map["Blue"]["count"]) == 6


def test_get_part_detail_no_ownership(tmp_path):
    db_path = str(tmp_path / "noown.db")
    with connection_ctx(db_path) as conn, conn:
        create_schema(conn)
        cur = conn.cursor()
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (1, "Black"))
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("P2", "Gadget", None))
        cur.execute("INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)", (1, "P2", 1, 2, 0, ""))

    vm = MainViewModel(db_path)
    info = vm.get_part_detail("P2")
    # counts should be 0 when no user_sets exist
    counts = info.get("counts")
    assert counts["total_pieces"] == 0
    assert counts["total_elements"] == 0
    # element count fields should be present and zero
    assert info["elements"][0].get("count", 0) == 0


def test_set_user_part_affects_totals(tmp_path):
    db_path = str(tmp_path / "userparts.db")
    with connection_ctx(db_path) as conn, conn:
        create_schema(conn)
        cur = conn.cursor()
        cur.execute("INSERT INTO colors (id, name) VALUES (?,?)", (1, "Black"))
        cur.execute("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", ("P3", "Thing", None))
        cur.execute("INSERT INTO inventories (id, version, set_num) VALUES (?,?,?)", (1, 1, "S1"))
        cur.execute("INSERT INTO inventory_parts (inventory_id, part_num, color_id, quantity, is_spare, img_url) VALUES (?,?,?,?,?,?)", (1, "P3", 1, 2, 0, ""))
        cur.execute("INSERT INTO user_sets (set_num, quantity, remark) VALUES (?,?,?)", ("S1", 1, ""))

    vm = MainViewModel(db_path)
    # initially total should be 2 (from set)
    info = vm.get_part_detail("P3")
    assert info["counts"]["total_pieces"] == 2

    # add 3 loose parts via set_user_part
    vm.set_user_part("P3", 1, 3)
    info = vm.get_part_detail("P3")
    # now total should be 5
    assert info["counts"]["total_pieces"] == 5
    # user_count should be reflected on element
    assert any(e.get("user_count", 0) == 3 for e in info["elements"]) is True


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
