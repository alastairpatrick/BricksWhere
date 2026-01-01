import sqlite3
from model.db import create_connection, create_schema, TABLES


import pytest

@pytest.mark.schema
def test_create_schema(sqlite_db):
    db, conn = sqlite_db
    cur = conn.cursor()
    # Ensure each expected table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    for t in TABLES:
        assert t in tables
