"""Functions to download Rebrickable CSV files and synchronize the local replica."""
import urllib.request
import gzip
import io
import csv
from typing import Iterable, Callable
from urllib.parse import urlparse
from .db import TABLES, bulk_replace_table

SYNC_URLS = [
    "https://cdn.rebrickable.com/media/downloads/themes.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/colors.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/part_categories.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/parts.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/part_relationships.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/elements.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/sets.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/minifigs.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/inventories.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/inventory_parts.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/inventory_sets.csv.gz",
    "https://cdn.rebrickable.com/media/downloads/inventory_minifigs.csv.gz",
]

# Validate URLs to prevent misuse and accidental downloads from other hosts
_ALLOWED_PREFIX = "https://cdn.rebrickable.com/media/downloads/"

# When enabled in developer mode, dev base url is set here so sync functions
# will map standard sync URLs to developer-hosted equivalents.
_DEV_BASE: str = None


def enable_dev_server(base_url: str):
    """Enable developer mode by setting the base URL for CSV downloads.

    `base_url` should be a URL ending with '/'. Example: 'http://127.0.0.1:8000/'.
    """
    global _DEV_BASE
    if base_url and not base_url.endswith('/'):
        base_url = base_url + '/'
    _DEV_BASE = base_url


def disable_dev_server():
    global _DEV_BASE
    _DEV_BASE = None

class InvalidUrlError(ValueError):
    pass


class SyncCancelled(Exception):
    """Raised when a synchronization is cancelled by the user."""
    pass


def validate_url(url: str) -> None:
    # Accept either the official Rebrickable prefix or the dev base if enabled
    ok = False
    if url.endswith('.csv.gz'):
        if url.startswith(_ALLOWED_PREFIX):
            ok = True
        if _DEV_BASE and url.startswith(_DEV_BASE):
            ok = True
    if not ok:
        raise InvalidUrlError(f"Disallowed or unexpected URL: {url}")


def _table_from_url(url: str) -> str:
    path = urlparse(url).path
    name = path.split('/')[-1]
    if name.endswith('.csv.gz'):
        name = name[:-7]
    if name not in TABLES:
        raise ValueError(f"Unexpected table name: {name}")
    return name


def download_csv_rows(url: str) -> Iterable[list[str]]:
    """Download and yield rows from the compressed CSV."""
    validate_url(url)
    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
        text = io.TextIOWrapper(gz, encoding='utf-8')
        reader = csv.reader(text)
        for row in reader:
            yield row


def sync_table_from_url(conn, url: str, is_cancelled: Callable = None) -> None:
    """Synchronize a single table from a Rebrickable CSV URL.

    Only columns present in our SCHEMA are kept; others are ignored.
    The table's content is replaced in a transactional way.
    """
    table = _table_from_url(url)
    rows = download_csv_rows(url)
    columns = next(rows)  # header row
    def progress(count):
        if is_cancelled is not None and is_cancelled():
            raise SyncCancelled()

    bulk_replace_table(conn, table, columns, rows, progress=progress)

def sync_all(conn, urls: Iterable[str] = None, progress: Callable[[str], None] = None, is_cancelled: Callable = None) -> None:
    """Synchronize all tables in `urls` sequentially.

    `progress` is an optional callback that receives status messages.
    """
    if urls is None:
        urls = SYNC_URLS
    # map to dev server urls when enabled
    if _DEV_BASE:
        mapped = []
        from urllib.parse import urlparse
        for u in urls:
            name = urlparse(u).path.split('/')[-1]
            mapped.append(_DEV_BASE + name)
        urls = mapped
    try:
        # begin a transaction that covers all table updates so we can rollback on cancel
        conn.execute("BEGIN")
        for u in urls:
            if is_cancelled is not None and is_cancelled():
                raise SyncCancelled()
            if progress:
                progress(f"Syncing {u}...")
            sync_table_from_url(conn, u, is_cancelled=is_cancelled)
            if progress:
                progress(f"Done {u}")
        conn.commit()
    except Exception:
        # rollback any partial changes
        try:
            conn.rollback()
        except Exception:
            pass
        raise
