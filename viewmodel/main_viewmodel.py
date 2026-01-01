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
            set_per_color = {row[0]: (row[1] or 0) for row in cur.fetchall()}

            # include user_parts (loose part quantities) per color
            cur.execute(
                "SELECT color_id, SUM(quantity) FROM user_parts WHERE part_num = ? GROUP BY color_id",
                (part_num,),
            )
            user_per_color = {row[0]: (row[1] or 0) for row in cur.fetchall()}

            # combine totals: sets + user_parts
            per_color_qty = {}
            all_color_ids = set(list(set_per_color.keys()) + list(user_per_color.keys()) + list(seen_colors.keys()))
            for cid in all_color_ids:
                per_color_qty[cid] = int(set_per_color.get(cid, 0) + user_per_color.get(cid, 0))

            # attach counts to elements (include both user_count and total count)
            total_pieces = 0
            total_elements = 0
            for el in elements:
                cid = el.get("color_id")
                user_qty = int(user_per_color.get(cid, 0))
                total_qty = int(per_color_qty.get(cid, 0))
                el["user_count"] = user_qty
                el["count"] = total_qty
                if total_qty > 0:
                    total_pieces += total_qty
                    total_elements += 1

            return {
                "part_num": pn,
                "name": name,
                "colors": colors,
                "elements": elements,
                "counts": {"total_pieces": total_pieces, "total_elements": total_elements, "per_color": per_color_qty},
            }

    def set_user_part(self, part_num: str, color_id: int, quantity: int) -> None:
        """Insert, update, or delete a `user_parts` record for a specific element.

        If `quantity` is zero, the row is deleted to avoid storing zeros.
        """
        with connection_ctx(self.db_path) as conn, conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM user_parts WHERE part_num = ? AND color_id = ?", (part_num, color_id))
            exists = cur.fetchone() is not None
            if quantity == 0:
                if exists:
                    cur.execute("DELETE FROM user_parts WHERE part_num = ? AND color_id = ?", (part_num, color_id))
            else:
                if exists:
                    cur.execute("UPDATE user_parts SET quantity = ? WHERE part_num = ? AND color_id = ?", (quantity, part_num, color_id))
                else:
                    cur.execute("INSERT INTO user_parts (part_num, color_id, quantity) VALUES (?,?,?)", (part_num, color_id, quantity))
            conn.commit()

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
