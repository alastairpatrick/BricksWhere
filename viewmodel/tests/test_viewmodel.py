import queue
import threading
from model.rebrickable import SyncCancelled
from viewmodel import DirectoryViewModel, MainViewModel, SyncViewModel
from model.db import create_connection, create_schema


import pytest


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


@pytest.mark.schema
def test_sync_viewmodel_runs_and_reports(sqlite_db):
    db, conn = sqlite_db

    msgs = []

    def fake_sync(conn, progress, cancel_event):
        # simulate writing a part and reporting progress
        progress("Downloading colors.csv.gz")
        cur = conn.cursor()
        cur.execute("INSERT INTO parts (part_num, name) VALUES (?,?)", ("PX", "TestPart"))
        conn.commit()
        progress("Finished colors")

    vm = SyncViewModel(str(db), sync_func=fake_sync)
    q = queue.Queue()
    cancel = threading.Event()
    vm.sync(q, cancel)

    # drain queue
    while not q.empty():
        msgs.append(q.get_nowait())

    assert any(m.startswith("Downloading") for m in msgs)
    assert "ALL_DONE" in msgs


@pytest.mark.schema
def test_syncviewmodel_start_async_and_join(sqlite_db):
    db, conn = sqlite_db

    def fake_sync(conn, progress, cancel_event):
        progress("A")
        progress("B")

    vm = SyncViewModel(str(db), sync_func=fake_sync)
    q = vm.start_async()

    msgs = []
    while True:
        try:
            msgs.append(q.get(timeout=0.5))
            if msgs[-1] == "ALL_DONE":
                break
        except Exception:
            break

    # wait for thread to finish
    vm.join()
    assert any(m == "A" for m in msgs)
    assert any(m == "B" for m in msgs)


@pytest.mark.schema
def test_syncviewmodel_cancel(sqlite_db):
    db, conn = sqlite_db

    def fake_sync(conn, progress, cancel_event):
        # block until cancel requested
        while not cancel_event.is_set():
            pass
        raise SyncCancelled()

    vm = SyncViewModel(str(db), sync_func=fake_sync)
    q = vm.start_async()
    # request cancellation
    vm.cancel()
    vm.join()
    # ensure ALL_DONE present and CANCELLED was sent
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    assert "ALL_DONE" in items


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


def test_sync_progress_viewmodel_processes_messages():
    from viewmodel import SyncProgressViewModel

    vm = SyncProgressViewModel(total_steps=4)
    q = queue.Queue()
    q.put("Step 1")
    q.put("Step 2")
    q.put("ALL_DONE")
    vm.process_queue(q)
    assert vm.entries == ["Step 1", "Step 2"]
    assert vm.ready_to_close is True
    assert vm.progress == min(100, int(2 * 100 / 4))


def test_directory_select_set_callback():
    called = []

    def on_select(selection):
        called.append(selection)

    vm = DirectoryViewModel(db_path=":memory:", on_selection_changed=on_select)
    vm.select_set("6001-1")
    assert called == [("SET", "6001-1")]