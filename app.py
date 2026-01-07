import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from requests_cache import CachedSession
import sys

from model.db import create_connection, create_schema, connection_ctx
from view import MainWindow

DB_PATH = "data.db"


def app_entry():
    # Parse CLI args for developer mode
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dev-server", nargs='?', const='dev_server', help="Enable developer mode and serve CSVs from local directory (optional directory path).")
    args = parser.parse_args()

    # Environment variable support
    env_dev_dir = os.environ.get("BRICKSW_DEV_DIR", None)

    # If developer mode requested via CLI or env var, start dev server
    dev_server = None
    if args.dev_server:
        from devserver import DevHTTPServer
        dev_dir = args.dev_server if args.dev_server != 'dev_server' else (env_dev_dir or "dev_server")
        # ensure directory exists
        if not os.path.isdir(dev_dir):
            os.makedirs(dev_dir, exist_ok=True)
        dev_server = DevHTTPServer(directory=dev_dir)
        dev_server.start()
        # instruct rebrickable to use dev base URL
        try:
            from model.rebrickable import enable_dev_server
            enable_dev_server(dev_server.base_url)
        except Exception:
            pass

    # Ensure DB exists
    db_exists = os.path.exists(DB_PATH)
    with connection_ctx(DB_PATH) as conn, conn:
        create_schema(conn)

    executor = ThreadPoolExecutor(max_workers=2)

    requests_session = CachedSession(
        backend='sqlite',
        cache_name=DB_PATH,
        cache_control=True,
    )

    app = QApplication(sys.argv)
    win = MainWindow(DB_PATH, executor=executor, requests_session=requests_session)

    # If DB was just created, automatically start initial sync
    if not db_exists:
        QTimer.singleShot(0, lambda: win.start_sync())

    win.show()
    try:
        sys.exit(app.exec())
    finally:
        # stop dev server if we started one
        if dev_server:
            try:
                from model.rebrickable import disable_dev_server
                disable_dev_server()
            except Exception:
                pass
            try:
                dev_server.stop()
            except Exception:
                pass


if __name__ == '__main__':
    app_entry()
