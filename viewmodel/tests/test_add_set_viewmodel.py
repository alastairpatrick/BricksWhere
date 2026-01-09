import pytest

from viewmodel.choose_set_viewmodel import ChooseSetViewModel


@pytest.mark.schema
def test_prefix_and_exists(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    cur.execute("INSERT INTO sets (set_num, name) VALUES (?,?)", ("A1", "Alpha"))
    cur.execute("INSERT INTO sets (set_num, name) VALUES (?,?)", ("A2", "Beta"))
    cur.execute("INSERT INTO sets (set_num, name) VALUES (?,?)", ("B1", "Gamma"))
    conn.commit()
    conn.close()

    vm = ChooseSetViewModel(db)
    matches = vm.prefix_matches("A")
    assert any(m[0] == "A1" for m in matches)
    assert vm.set_exists("A1")
    assert not vm.set_exists("Z")