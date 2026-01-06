import sqlite3
from contextlib import closing
from model.db import create_connection


class SetsViewModel:
    """ViewModel for user_sets UI. Provides CRUD operations for user_sets.

    Methods are kept small and testable.
    """
    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path

    def list_user_sets(self, order_by: str = "set_num", descending: bool = False):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            dir = "DESC" if descending else "ASC"
            # map allowed order_by values to qualified column names to avoid ambiguity
            mapping = {
                "set_num": "u.set_num",
                # fall back to set_num when sets.name is missing
                "name": "COALESCE(s.name, u.set_num)",
                "quantity": "u.quantity",
                "remark": "u.remark",
            }
            order_col = mapping.get(order_by, "u.set_num")
            sql = (
                "SELECT u.set_num, COALESCE(s.name, u.set_num), COALESCE(u.quantity,0), COALESCE(u.remark,'') "
                "FROM user_sets u LEFT JOIN sets s ON u.set_num = s.set_num "
                f"ORDER BY {order_col} {dir}"
            )
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {"set_num": r[0], "name": r[1], "quantity": r[2], "remark": r[3]} for r in rows
            ]

    def add_user_set(self, set_num: str, quantity: int = 1, remark: str = ""):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO user_sets (set_num, quantity, remark) VALUES (?,?,?)", (set_num, quantity, remark))

    def update_user_set(self, set_num: str, quantity: int, remark: str):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("UPDATE user_sets SET quantity = ?, remark = ? WHERE set_num = ?", (quantity, remark, set_num))

    def update_set_num(self, old_set_num: str, new_set_num: str):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("UPDATE user_sets SET set_num = ? WHERE set_num = ?", (new_set_num, old_set_num))

    def delete_user_set(self, set_num: str):
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_sets WHERE set_num = ?", (set_num,))
