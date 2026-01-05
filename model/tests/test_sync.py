import pytest
import threading
from model.db import create_connection
from model import rebrickable


@pytest.mark.schema
def test_sync_colors(monkeypatch, sqlite_db):
    db, conn = sqlite_db

    # define sample rows as dicts
    sample = [
        ["id", "name", "rgb", "is_trans", "num_parts", "num_sets", "y1", "y2"],
        ["1", "Black", "000000", "0", "10", "5", "1950", ""],
        ["2", "Blue", "0000FF", "0", "20", "10", "1960", ""],
    ]

    def fake_download(url):
        assert url.endswith("colors.csv.gz")
        for r in sample:
            yield r

    monkeypatch.setattr(rebrickable, "download_csv_rows", fake_download)
    url = "https://cdn.rebrickable.com/media/downloads/colors.csv.gz"
    # call sync for colors table
    rebrickable.sync_table_from_url(conn, url)

    cur = conn.cursor()
    cur.execute("SELECT id, name, rgb, num_parts FROM colors ORDER BY id")
    rows = cur.fetchall()
    assert rows[0][1] == "Black"
    assert rows[1][2] == "0000FF"
    # connection closed by fixture


def test_invalid_url_raises():
    import pytest
    with pytest.raises(rebrickable.InvalidUrlError):
        list(rebrickable.download_csv_rows("http://example.com/bad.csv.gz"))


def test_coerce_row_preserves_text_ids():
    from model.db import coerce_row
    # simulate parts table where part_num looks numeric but must be text
    row = ["03497", "Widget", "1", "ABS"]
    vals = coerce_row(row, ["part_num", "name", "part_cat_id", "part_material"], table="parts")
    # first element should remain the string '03497', not integer 3497
    assert vals[0] == "03497"
    # integer field part_cat_id should be converted to int
    assert isinstance(vals[2], int) and vals[2] == 1


@pytest.mark.schema
def test_sync_cancel_rollback(monkeypatch, sqlite_db):
    # verify that cancelling a sync causes a rollback (no partial writes)
    db, conn = sqlite_db

    cancel_event = threading.Event()

    # fake download: produce one row then request cancellation
    def fake_download(url):
        yield {"id": "1", "name": "Black", "rgb": "000000", "is_trans": "0", "num_parts": "10", "num_sets": "5", "y1": "1950", "y2": ""}
        cancel_event.set()

    monkeypatch.setattr(rebrickable, "download_csv_rows", fake_download)
    urls = ["https://cdn.rebrickable.com/media/downloads/colors.csv.gz", "https://cdn.rebrickable.com/media/downloads/parts.csv.gz"]
    import pytest
    with pytest.raises(rebrickable.SyncCancelled):
        rebrickable.sync_all(conn, urls=urls, progress=lambda m: None, is_cancelled=cancel_event.is_set)

    # ensure colors table is empty because transaction should have been rolled back
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM colors")
    assert cur.fetchone()[0] == 0
    # connection closed by fixture
