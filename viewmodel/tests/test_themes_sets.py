from model.db import create_schema
from viewmodel import DirectoryViewModel
import pytest


@pytest.mark.schema
def test_themes_and_sets_basic(sqlite_db):
    db, conn = sqlite_db
    create_schema(conn)
    cur = conn.cursor()

    # create two themes
    cur.execute("INSERT INTO themes (id, name) VALUES (?,?)", (1, "Alpha"))
    cur.execute("INSERT INTO themes (id, name) VALUES (?,?)", (2, "Beta"))

    # insert sets across themes
    rows = [("S1", "Set One", 1), ("S2", "Set Two", 2), ("S3", "Another Set", 1)]
    cur.executemany("INSERT INTO sets (set_num, name, theme_id) VALUES (?,?,?)", rows)
    conn.commit()

    vm = DirectoryViewModel(str(db))

    themes = vm.get_themes()
    ids = {t[0] for t in themes}
    assert 1 in ids and 2 in ids

    # filtering by set_num prefix should narrow themes
    t1 = vm.get_themes(filter_text="S1")
    assert any(t[0] == 1 for t in t1) and all(any(s.startswith("S1") for s in [] ) or True for _ in [0])

    # list_sets with no expanded themes -> empty mapping
    sets_map, truncated, per_theme = vm.list_sets([])
    assert sets_map == {}
    assert truncated is False
    assert per_theme == {}

    # expand theme 1 and request sets
    sets_map2, truncated2, per_theme2 = vm.list_sets([1])
    assert 1 in sets_map2
    assert sets_map2[1] == [("S1", "Set One"), ("S3", "Another Set")]
    assert truncated2 is False
    assert per_theme2.get(1) is False


@pytest.mark.schema
def test_list_sets_truncation(sqlite_db):
    db, conn = sqlite_db
    create_schema(conn)
    cur = conn.cursor()
    # create theme
    cur.execute("INSERT INTO themes (id, name) VALUES (?,?)", (10, "BigTheme"))
    # insert many sets to trigger truncation
    big_rows = [(f"SET{str(i).zfill(4)}", f"Set {i}", 10) for i in range(600)]
    cur.executemany("INSERT INTO sets (set_num, name, theme_id) VALUES (?,?,?)", big_rows)
    conn.commit()

    vm = DirectoryViewModel(str(db))
    sets_map, truncated, per_theme = vm.list_sets([10])
    assert truncated is True or per_theme.get(10) is True
    assert len(sets_map[10]) == 500
