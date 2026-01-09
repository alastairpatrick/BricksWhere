from model.db import create_connection


class ChooseSetViewModel:
    """ViewModel for ChooseSetDialog. Provides DB-backed lookup methods.

    Methods are small and testable. Tests can instantiate with a temporary
    database created by the test fixture.
    """

    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path

    def prefix_matches(self, prefix: str, limit: int = 101):
        """Return a list of (set_num, name) for sets whose set_num starts with prefix.

        Returns at most `limit` rows.
        """
        if prefix is None:
            return []
        p = prefix + "%"
        try:
            conn = create_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT set_num, name FROM sets WHERE set_num LIKE ? ESCAPE '\\' LIMIT ?", (p, limit))
            rows = cur.fetchall()
            conn.close()
            return rows
        except Exception:
            return []

    def set_exists(self, set_num: str) -> bool:
        if not set_num:
            return False
        try:
            conn = create_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM sets WHERE set_num = ? LIMIT 1", (set_num,))
            found = cur.fetchone() is not None
            conn.close()
            return found
        except Exception:
            return False
