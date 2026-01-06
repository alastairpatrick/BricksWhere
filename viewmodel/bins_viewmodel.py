import sqlite3
import sqlite3
from contextlib import closing
from model.db import create_connection


class BinsViewModel:
    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path

    def list_user_part_bins(self, order_by: str = "part_num", descending: bool = False):
        try:
            with closing(create_connection(self.db_path)) as conn, conn:
                cur = conn.cursor()
                dir = "DESC" if descending else "ASC"
                mapping = {
                    "part_num": "u.part_num",
                    "bin_num": "u.bin_num",
                    "remark": "u.remark",
                }
                order_col = mapping.get(order_by, "u.part_num")
                sql = (
                    "SELECT u.part_num, COALESCE(u.bin_num, ''), COALESCE(u.remark, '') "
                    "FROM user_part_bins u "
                    f"ORDER BY {order_col} {dir}"
                )
                cur.execute(sql)
                rows = cur.fetchall()
                return [{"part_num": r[0], "bin_num": r[1], "remark": r[2]} for r in rows]
        except sqlite3.OperationalError:
            # If the database or table isn't present (e.g., during some tests),
            # return an empty list rather than raising so the UI can initialize.
            return []

    def add_user_part_bin(self, part_num: str, bin_num: str = None, remark: str = ""):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO user_part_bins (part_num, bin_num, remark) VALUES (?,?,?)", (part_num, bin_num, remark))

    def update_user_part_bin(self, part_num: str, bin_num: str, remark: str):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("UPDATE user_part_bins SET bin_num = ?, remark = ? WHERE part_num = ?", (bin_num, remark, part_num))

    def update_part_num(self, old_part_num: str, new_part_num: str):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("UPDATE user_part_bins SET part_num = ? WHERE part_num = ?", (new_part_num, old_part_num))

    def delete_user_part_bin(self, part_num: str):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_part_bins WHERE part_num = ?", (part_num,))
