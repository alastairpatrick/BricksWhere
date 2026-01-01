"""Database utilities for LEGOwhere.

Provides functions to create an SQLite database and the replica tables
that map to Rebrickable CSV files. Use parameterized SQL for inserts to
avoid SQL injection and validate column names from CSV headers.
"""
import itertools
import sqlite3
from contextlib import closing
import re
import threading
from typing import Iterable, Sequence, Tuple

# Allowed identifier characters for column names (letters, digits, underscore)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def sanitize_identifier(name: str) -> str:
    """Return a safe column or table name or raise ValueError if invalid."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid identifier: {name}")
    return name

# Define the schema for the replica tables according to corrected design.md
# Each entry maps a table name to a list of (column_name, sql_type, is_primary)
SCHEMA = {
    "colors": [
        ("id", "INTEGER", True),
        ("name", "TEXT", False),
        ("rgb", "TEXT", False),
        ("is_trans", "INTEGER", False),
        ("num_parts", "INTEGER", False),
        ("num_sets", "INTEGER", False),
        ("y1", "INTEGER", False),
        ("y2", "INTEGER", False),
    ],
    "part_categories": [("id", "INTEGER", True), ("name", "TEXT", False)],
    "parts": [
        ("part_num", "TEXT", True),
        ("name", "TEXT", False),
        ("part_cat_id", "INTEGER", False),
        ("part_material", "TEXT", False),
    ],
    "elements": [
        ("element_id", "TEXT", True),
        ("part_num", "TEXT", False),
        ("color_id", "INTEGER", False),
        ("design_id", "TEXT", False),
    ],
    "themes": [("id", "INTEGER", True), ("name", "TEXT", False), ("parent_id", "INTEGER", False)],
    "sets": [
        ("set_num", "TEXT", True),
        ("name", "TEXT", False),
        ("year", "INTEGER", False),
        ("theme_id", "INTEGER", False),
        ("num_parts", "INTEGER", False),
        ("img_url", "TEXT", False),
    ],
    "user_sets": [
        ("set_num", "TEXT", True),
        ("quantity", "INTEGER", False),
        ("remark", "TEXT", False),
    ],
    "minifigs": [("fig_num", "TEXT", True), ("name", "TEXT", False), ("num_parts", "INTEGER", False), ("img_url", "TEXT", False)],
    "inventories": [("id", "INTEGER", True), ("version", "INTEGER", False), ("set_num", "TEXT", False)],
    "inventory_parts": [
        ("inventory_id", "INTEGER", False),
        ("part_num", "TEXT", False),
        ("color_id", "INTEGER", False),
        ("quantity", "INTEGER", False),
        ("is_spare", "INTEGER", False),
        ("img_url", "TEXT", False),
    ],
    "inventory_sets": [("inventory_id", "INTEGER", False), ("set_num", "TEXT", False), ("quantity", "INTEGER", False)],
    "inventory_minifigs": [("inventory_id", "INTEGER", False), ("fig_num", "TEXT", False), ("quantity", "INTEGER", False)],
    "part_relationships": [("rel_type", "TEXT", False), ("child_part_num", "TEXT", False), ("parent_part_num", "TEXT", False)],
}

# table -> list of column names to index. Non-primary keys only. If a table is not listed, no non-primary indexes are created.
SECONDARY_INDEXES = {
    "parts": ["part_cat_id"],
    "elements": ["part_num", "color_id"],
    "themes": ["parent_id"],
    "sets": ["theme_id"],
    "inventories": ["set_num"],
    "inventory_parts": ["inventory_id", "part_num", "color_id"],
    "inventory_sets": ["inventory_id", "set_num"],
    "inventory_minifigs": ["inventory_id", "fig_num"],
}

def create_connection(path: str) -> sqlite3.Connection:
    """Return a sqlite3 connection. Foreign keys enabled."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_table_sql(table: str) -> str:
    """Return a CREATE TABLE SQL for a sanitized schema."""
    cols = []
    pks = []
    for name, coltype, is_pk in SCHEMA[table]:
        sanitize_identifier(name)
        cols.append(f"{name} {coltype}")
        if is_pk:
            pks.append(name)
    pk_sql = f", PRIMARY KEY({', '.join(pks)})" if pks else ""
    return f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(cols)}{pk_sql})"

def create_secondary_indexes_sql(table: str) -> Iterable[str]:
    """Yield CREATE INDEX statements for non-primary secondary keys (if applicable).
    """
    for name in SECONDARY_INDEXES.get(table, []):
        sanitize_identifier(name)
        yield f"CREATE INDEX IF NOT EXISTS idx_{table}_{name} ON {table}({name})"

def drop_secondary_indexes_sql(table: str) -> Iterable[str]:
    """Yield DROP INDEX statements for non-primary secondary keys (if applicable).
    """
    for name in SECONDARY_INDEXES.get(table, []):
        sanitize_identifier(name)
        yield f"DROP INDEX IF EXISTS idx_{table}_{name}"

def create_schema(conn: sqlite3.Connection) -> None:
    """Create all replica tables and indexes based on SCHEMA."""
    cur = conn.cursor()
    for table in SCHEMA.keys():
        sql = create_table_sql(table)
        cur.execute(sql)
        for idx_sql in create_secondary_indexes_sql(table):
            cur.execute(idx_sql)
    conn.commit()

def _batched_old(iterable: Iterable, n: int):
    iterator = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(iterator, n))
        if not chunk:
            return
        yield chunk

def bulk_replace_table(conn: sqlite3.Connection, table: str, columns: Sequence[str], rows: Iterable[Sequence], progress = None) -> None:
    """Replace contents of `table` with provided rows in a single transaction.

    Uses parameterized INSERT to avoid SQL injection. Column names are expected to be
    already validated.
    """
    sanitize_identifier(table)
    for c in columns:
        sanitize_identifier(c)
    col_list = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(columns))

    # For large tables like inventory_parts, it's much faster to drop indexes,
    # bulk insert, then recreate indexes than to keep indexes during inserts.
    # The progress callback, if provided, can raise an excepton to cancel, rolling
    # back the transaction.
    cur = conn.cursor()
    for idx_sql in drop_secondary_indexes_sql(table):
        cur.execute(idx_sql)
    cur.execute(f"DELETE FROM {table}")

    ins = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    batch_size = 10000
    for batch in _batched_old(rows, batch_size):
        batch = list(map(lambda r: coerce_row(r, columns, table=table), batch))
        cur.executemany(ins, batch)
        if progress is not None:
            progress(len(batch))
    for idx_sql in create_secondary_indexes_sql(table):
        cur.execute(idx_sql)

# Minimal helper to coerce booleans and empty strings from CSV into SQLite types
def coerce_row(row: Sequence[str], columns: Sequence[str], table: str = None) -> Tuple:
    """Coerce CSV string values to Python types based on SCHEMA for `table`.

    If `table` is provided, use SCHEMA to decide which columns are INTEGER and
    coerce only those to int. Textual columns (like part_num) are left as strings
    to preserve leading zeros and avoid accidental duplicates.
    """
    vals = []
    # build a map of column->type if table provided
    col_types = {}
    if table and table in SCHEMA:
        for name, coltype, _pk in SCHEMA[table]:
            col_types[name] = coltype.upper()
    for c, v in zip(columns, row):
        if v == "":
            vals.append(None)
            continue
        t = col_types.get(c, "TEXT")
        if t == "INTEGER":
            # treat booleans and numeric strings
            if isinstance(v, str) and v.lower() in ("true", "false"):
                vals.append(1 if v.lower() == "true" else 0)
                continue
            # try integer conversion, otherwise leave as-is and let SQLite coerce
            try:
                vals.append(int(v))
                continue
            except Exception:
                vals.append(v)
                continue
        # otherwise keep textual value as-is
        vals.append(v)
    return tuple(vals)

# Expose SCHEMA keys for other modules
TABLES = list(SCHEMA.keys())


def connection_ctx(path: str):
    """Return a context manager yielding a sqlite3.Connection.

    Use as: ``with connection_ctx(path) as conn:``. The connection will be
    closed on exit (even if an exception occurs).
    """
    return closing(create_connection(path))
