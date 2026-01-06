import sqlite3
import pytest
from viewmodel.bins_viewmodel import BinsViewModel


@pytest.mark.schema
def test_add_list_delete(sqlite_db):
    db, conn = sqlite_db
    conn.close()
    vm = BinsViewModel(db)
    vm.add_user_part_bin("P1", "A1", "r")
    rows = vm.list_user_part_bins()
    assert len(rows) == 1
    assert rows[0]["part_num"] == "P1"
    vm.delete_user_part_bin("P1")
    rows = vm.list_user_part_bins()
    assert rows == []


@pytest.mark.schema
def test_add_duplicate_raises(sqlite_db):
    db, conn = sqlite_db
    conn.close()
    vm = BinsViewModel(db)
    vm.add_user_part_bin("DUP", "B1", "x")
    with pytest.raises(sqlite3.IntegrityError):
        vm.add_user_part_bin("DUP", "B2", "y")


@pytest.mark.schema
def test_update_part_num(sqlite_db):
    db, conn = sqlite_db
    conn.close()
    vm = BinsViewModel(db)
    vm.add_user_part_bin("OLD", "B", "r")
    vm.update_part_num("OLD", "NEW")
    rows = vm.list_user_part_bins()
    assert rows[0]["part_num"] == "NEW"
