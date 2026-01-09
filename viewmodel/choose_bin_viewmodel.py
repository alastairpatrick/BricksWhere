from contextlib import closing
from model.db import create_connection


class ChooseBinViewModel:
    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path

    def prefix_matches(self, prefix: str, limit: int = 50):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            like = f"{prefix}%"
            cur.execute("SELECT part_num, COALESCE(name,'') FROM parts WHERE part_num LIKE ? ORDER BY part_num LIMIT ?", (like, limit))
            return cur.fetchall()

    def part_exists(self, part_num: str):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM parts WHERE part_num = ?", (part_num,))
            return cur.fetchone() is not None
