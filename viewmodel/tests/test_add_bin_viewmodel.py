import pytest

from viewmodel.add_bin_viewmodel import AddBinViewModel


@pytest.mark.schema
def test_prefix_and_exists(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    cur.execute("INSERT INTO parts (part_num, name) VALUES (?,?)", ("P1", "Part One"))
    cur.execute("INSERT INTO parts (part_num, name) VALUES (?,?)", ("P2", "Part Two"))
    cur.execute("INSERT INTO parts (part_num, name) VALUES (?,?)", ("Q1", "Other"))
    conn.commit()
    conn.close()

    vm = AddBinViewModel(db)
    matches = vm.prefix_matches("P")
    assert any(m[0] == "P1" for m in matches)
    assert vm.part_exists("P1")
    assert not vm.part_exists("Z")
