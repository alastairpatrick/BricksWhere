import os
from model.db import create_connection, create_schema, connection_ctx
from viewmodel import MainViewModel


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
