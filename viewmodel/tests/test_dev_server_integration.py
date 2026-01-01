import gzip
import os
import sqlite3
import tempfile
from devserver import DevHTTPServer
from model.db import create_connection, create_schema
from model import rebrickable


def make_gz_csv(path, header, rows):
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        f.write(header + '\n')
        for r in rows:
            f.write(','.join(r) + '\n')


def test_dev_server_and_sync(tmp_path):
    # prepare a small dev data dir with just colors.csv.gz
    dev_dir = tmp_path / "dev_data"
    dev_dir.mkdir()
    colors = dev_dir / "colors.csv.gz"
    header = "id,name,rgb,is_trans,num_parts,num_sets,y1,y2"
    rows = [["1", "Black", "000000", "0", "1", "1", "1950", ""], ["2", "Blue", "0000FF", "0", "1", "1", "1960", ""]]
    make_gz_csv(str(colors), header, rows)

    # start dev server
    server = DevHTTPServer(directory=str(dev_dir))
    server.start()
    try:
        rebrickable.enable_dev_server(server.base_url)

        # sync just the colors table by calling sync_all with the default URL (it will be mapped)
        db = tmp_path / "test.db"
        conn = create_connection(str(db))
        try:
            create_schema(conn)
            rebrickable.sync_all(conn, urls=[rebrickable.SYNC_URLS[1]])

            cur = conn.cursor()
            cur.execute("SELECT id, name FROM colors ORDER BY id")
            got = cur.fetchall()
            assert got[0][1] == "Black"
            assert got[1][1] == "Blue"
        finally:
            conn.close()
    finally:
        rebrickable.disable_dev_server()
        server.stop()