import sqlite3
import pytest
from viewmodel.sets_viewmodel import SetsViewModel


@pytest.mark.schema
def test_add_list_delete(sqlite_db):
    db, conn = sqlite_db
    # insert a set into sets table for name lookup
    cur = conn.cursor()
    cur.execute("INSERT INTO sets (set_num, name) VALUES (?,?)", ("S1", "Set One"))
    conn.commit()
    conn.close()

    vm = SetsViewModel(db)
    vm.add_user_set("S1", 2, "note")
    rows = vm.list_user_sets()
    assert len(rows) == 1
    assert rows[0]["set_num"] == "S1"
    assert rows[0]["name"] == "Set One"

    vm.delete_user_set("S1")
    rows = vm.list_user_sets()
    assert rows == []


@pytest.mark.schema
def test_add_duplicate_raises(sqlite_db):
    db, conn = sqlite_db
    vm = SetsViewModel(db)
    vm.add_user_set("DUP", 1, "r")
    with pytest.raises(sqlite3.IntegrityError):
        vm.add_user_set("DUP", 2, "r2")


@pytest.mark.schema
def test_update_set_num(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    cur.execute("INSERT INTO sets (set_num, name) VALUES (?,?)", ("A1", "A One"))
    conn.commit()
    conn.close()

    vm = SetsViewModel(db)
    vm.add_user_set("A1", 1, "x")
    vm.update_set_num("A1", "B1")
    rows = vm.list_user_sets()
    assert rows[0]["set_num"] == "B1"