import time
import pytest
from concurrent.futures import Future
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from model.db import create_connection, create_schema, connection_ctx


def pytest_configure(config):
    # register a convenience marker so tests can request automatic schema
    config.addinivalue_line("markers", "schema: create database schema automatically for sqlite_db fixture")


@pytest.fixture(scope="session")
def _session_app_qt():
    assert QApplication.instance() is None, "A QApplication instance already exists before tests start"
    return QApplication([])

@pytest.fixture
def app_qt(_session_app_qt):
    yield _session_app_qt


@pytest.fixture
def flush_events(app_qt):
    """Helper tests can call to process Qt events for a short while.

    Using this is preferable to unconditionally calling `processEvents()` in
    the global teardown because executing events during teardown can exercise
    dangling Qt objects and cause native crashes. Tests should call this
    helper when they need to flush pending Qt events.
    """
    def _flush(timeout=0.05):
        import time
        deadline = time.time() + float(timeout)
        while time.time() < deadline:
            try:
                app_qt.processEvents()
            except Exception:
                pass
    return _flush

class FakeExecutor:
    """A fake executor that runs tasks on the main thread for testing."""

    def __init__(self, app, timeout=5.0):
        self._pending_count = 0
        self._app = app
        self._timeout = timeout

    def submit(self, fn, *args, **kwargs):
        future = Future()
        self._pending_count += 1
        def deferred():
            try:
                result = fn(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self._pending_count -= 1
        QTimer.singleShot(0, deferred)
        return future
    
    def drain_all(self):
        """Await completion of all pending tasks."""
        start_time = time.time()
        while self._pending_count > 0:
            if time.time() - start_time > self._timeout:
                raise TimeoutError("Timed out waiting for FakeExecutor tasks to complete")  
            self._app.processEvents()

@pytest.fixture
def executor(app_qt):
    executor = FakeExecutor(app_qt)
    yield executor
    executor.drain_all()

@pytest.fixture
def sqlite_db(tmp_path, request):
    """Create a sqlite database file and connection for tests.

    Optionally the caller may parametrize the fixture to request automatic
    schema creation. Example usage:

        @pytest.mark.schema
        def test_x(sqlite_db):
            db_path, conn = sqlite_db

    The fixture yields a tuple (db_path_str, connection). The connection is
    closed automatically when the fixture scope ends.
    """
    db = str(tmp_path / "test.db")
    conn = create_connection(db)
    try:
        # WAL mode seems to make setup time for tests that use this fixture faster
        conn.execute("PRAGMA journal_mode = WAL")

        # Optional convenience marker on the test to request schema creation
        if request.node.get_closest_marker("schema"):
            create_schema(conn)

        yield db, conn

    finally:
        conn.close()
