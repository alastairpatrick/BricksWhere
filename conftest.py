import pytest
from model.db import create_connection, create_schema, connection_ctx


def pytest_configure(config):
    # register a convenience marker so tests can request automatic schema
    config.addinivalue_line("markers", "schema: create database schema automatically for sqlite_db fixture")


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
        # Optional convenience marker on the test to request schema creation
        if request.node.get_closest_marker("schema"):
            create_schema(conn)

        yield db, conn

    finally:
        conn.close()
