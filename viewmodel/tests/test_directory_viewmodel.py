from model.db import create_schema


import pytest

from viewmodel.directory_viewmodel import DirectoryViewModel


@pytest.mark.schema
def test_directory_list_limits_and_search(sqlite_db):
    db, conn = sqlite_db
    create_schema(conn)
    cur = conn.cursor()
    # create a category and assign all parts to it
    cur.execute("INSERT INTO part_categories (id, name) VALUES (?,?)", (1, "Default"))

    # insert 600 parts in category 1
    rows = [(f"P{str(i).zfill(4)}", f"Part {i}", 1) for i in range(600)]
    cur.executemany("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", rows)
    conn.commit()

    vm = DirectoryViewModel(str(db))
    parts_map, truncated, per_cat = vm.list_parts([1])
    assert len(parts_map[1]) == 500
    assert truncated is True

    # search for specific prefix within expanded category
    hits_map, t2, per_cat2 = vm.list_parts([1], filter_text="P0001")
    assert any(p[0].startswith("P0001") for p in hits_map.get(1, []))
    assert t2 is False


@pytest.mark.schema
def test_directory_debounce_and_selection_callbacks(sqlite_db):
    db, conn = sqlite_db

    applied = []
    selected = []

    def on_search(text):
        applied.append(text)

    def on_select(part):
        selected.append(part)

    vm = DirectoryViewModel(str(db), debounce_ms=0, on_search_applied=on_search, on_selection_changed=on_select)
    vm.set_search_text("P")
    # debounce_ms=0 should apply immediately
    assert applied == ["P"]

    # selection should invoke callback
    vm.select_part("P0001")
    assert selected == [("PART", "P0001")]


@pytest.mark.schema
def test_directory_categories_and_expansion(sqlite_db):
    db, conn = sqlite_db
    create_schema(conn)

    # create two categories
    cur = conn.cursor()
    cur.execute("INSERT INTO part_categories (id, name) VALUES (?,?)", (1, "Alpha"))
    cur.execute("INSERT INTO part_categories (id, name) VALUES (?,?)", (2, "Beta"))

    # insert parts across categories
    rows = [("A1", "Part A1", 1), ("A2", "Part A2", 1), ("B1", "Part B1", 2)]
    cur.executemany("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", rows)
    conn.commit()

    vm = DirectoryViewModel(str(db))

    cats = vm.get_categories()
    assert (1, "Alpha") in cats and (2, "Beta") in cats

    # no expanded categories -> empty mapping
    parts_map, truncated, per_cat = vm.list_parts([])
    assert parts_map == {}
    assert truncated is False
    assert per_cat == {}

    # expand category 1 and request parts for it
    parts_map2, truncated2, per_cat2 = vm.list_parts([1])
    assert 1 in parts_map2
    assert parts_map2[1] == [("A1", "Part A1"), ("A2", "Part A2")]
    assert truncated2 is False
    assert per_cat2.get(1) is False

    # test truncation when many parts in one category
    # add 600 parts to category 1
    big_rows = [(f"P{str(i).zfill(4)}", f"Part {i}", 1) for i in range(600)]
    cur.executemany("INSERT INTO parts (part_num, name, part_cat_id) VALUES (?,?,?)", big_rows)
    conn.commit()

    parts_map3, truncated3, per_cat3 = vm.list_parts([1])
    # should be truncated to 500 entries in the returned mapping for cat 1
    assert truncated3 is True
    assert len(parts_map3[1]) == 500
    assert per_cat3.get(1) is True


def test_directory_select_set_callback():
    called = []

    def on_select(selection):
        called.append(selection)

    vm = DirectoryViewModel(db_path=":memory:", on_selection_changed=on_select)
    vm.select_set("6001-1")
    assert called == [("SET", "6001-1")]