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
            # build elements list (unique colors) with image urls
            elements = []
            seen_colors = {}
            for color_id, img_url, color_name in cur.fetchall():
                if color_id in seen_colors:
                    continue
                seen_colors[color_id] = color_name
                elements.append({"color": color_name, "img_url": img_url, "color_id": color_id})

            # compute per-color quantities based on user_sets ownership
            # For each inventory that corresponds to a set the user owns, multiply
            # inventory_part.quantity by user_sets.quantity and sum per color
            cur.execute(
                """
                SELECT ip.color_id, SUM(ip.quantity * us.quantity) as qty
                FROM inventory_parts ip
                JOIN inventories inv ON ip.inventory_id = inv.id
                JOIN user_sets us ON us.set_num = inv.set_num
                WHERE ip.part_num = ? AND us.quantity > 0
                GROUP BY ip.color_id
                """,
                (part_num,),
            )
            per_color_qty = {row[0]: (row[1] or 0) for row in cur.fetchall()}

            # attach counts to elements
            total_pieces = 0
            total_elements = 0
            for el in elements:
                cid = el.get("color_id")
                qty = per_color_qty.get(cid, 0)
                el["count"] = int(qty)
                if qty > 0:
                    total_pieces += int(qty)
                    total_elements += 1

            return {
                "part_num": pn,
                "name": name,
                "colors": colors,
                "elements": elements,
                "counts": {"total_pieces": total_pieces, "total_elements": total_elements, "per_color": per_color_qty},
            }

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
