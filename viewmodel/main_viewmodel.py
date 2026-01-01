from model.db import create_connection, connection_ctx


class MainViewModel:
    """Provide detailed part info for the main view."""
    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path

    def get_part_detail(self, part_num: str) -> dict:
        with connection_ctx(self.db_path) as conn, conn:
            cur = conn.cursor()
            cur.execute("SELECT part_num, name FROM parts WHERE part_num = ?", (part_num,))
            row = cur.fetchone()
            if not row:
                return {}
            pn, name = row
            cur.execute(
                "SELECT c.name FROM elements e JOIN colors c ON e.color_id = c.id WHERE e.part_num = ? ORDER BY c.name",
                (part_num,),
            )
            colors = [r[0] for r in cur.fetchall()]
            # also fetch inventory parts image urls and associated color names
            cur.execute(
                "SELECT ip.color_id, ip.img_url, c.name FROM inventory_parts ip JOIN colors c ON ip.color_id = c.id WHERE ip.part_num = ? ORDER BY c.name",
                (part_num,),
            )
            elements = []
            seen_colors = set()
            for color_id, img_url, color_name in cur.fetchall():
                if color_id in seen_colors:
                    continue
                seen_colors.add(color_id)
                elements.append({"color": color_name, "img_url": img_url})
            return {"part_num": pn, "name": name, "colors": colors, "elements": elements}

    def get_set_detail(self, set_num: str) -> dict:
        with connection_ctx(self.db_path) as conn, conn:
            cur = conn.cursor()
            cur.execute("SELECT set_num, name, img_url FROM sets WHERE set_num = ?", (set_num,))
            row = cur.fetchone()
            if not row:
                return {}
            sn, name, img_url = row
            return {"set_num": sn, "name": name, "img_url": img_url}

    def get_user_set(self, set_num: str) -> dict:
        """Return user provided data for a set, defaults to quantity=0 and remark="" if not present."""
        with connection_ctx(self.db_path) as conn, conn:
            cur = conn.cursor()
            cur.execute("SELECT set_num, quantity, remark FROM user_sets WHERE set_num = ?", (set_num,))
            row = cur.fetchone()
            if not row:
                return {"set_num": set_num, "quantity": 0, "remark": ""}
            sn, qty, remark = row
            return {"set_num": sn, "quantity": qty or 0, "remark": remark or ""}

    def set_user_set(self, set_num: str, quantity: int, remark: str) -> None:
        """Insert or update a user_sets record for `set_num`."""
        with connection_ctx(self.db_path) as conn, conn:
            cur = conn.cursor()
            # check existence
            cur.execute("SELECT 1 FROM user_sets WHERE set_num = ?", (set_num,))
            if cur.fetchone():
                cur.execute("UPDATE user_sets SET quantity = ?, remark = ? WHERE set_num = ?", (quantity, remark, set_num))
            else:
                cur.execute("INSERT INTO user_sets (set_num, quantity, remark) VALUES (?,?,?)", (set_num, quantity, remark))
            conn.commit()
