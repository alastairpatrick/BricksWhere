from typing import List, Optional, Tuple, Dict
import threading

import logging

from contextlib import closing
from model.db import create_connection

logger = logging.getLogger(__name__)


class DirectoryViewModel:
    """Provide part listing and search functionality."""
    def __init__(self, db_path: str = "data.db", debounce_ms: int = 200, on_search_applied=None, on_selection_changed=None):
        """db_path: path to sqlite db

        debounce_ms: milliseconds to wait after set_search_text before applying the search
        on_search_applied: optional callback(text) invoked when debounced search is applied
        on_selection_changed: optional callback(part_num) invoked when selection changes
        """
        self.db_path = db_path
        self._debounce_ms = debounce_ms
        self._on_search_applied = on_search_applied
        self._on_selection_changed = on_selection_changed
        self._search_timer = None
        self._pending_search = None
        # `_selected` is a tuple representing selection type and id, e.g. ("PART","P0001") or ("SET","6001-1")
        self._selected = None

    def get_categories(self, filter_text: str = "") -> List[Tuple[int, str]]:
        """Return list of (id, name) for categories that contain at least one part.

        If `filter_text` is provided, only categories that contain parts matching
        the filter (part_num prefix or name contains) are returned. Results are
        ordered by category name.
        """
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            if filter_text:
                # categories that have at least one matching part
                cur.execute(
                    "SELECT DISTINCT pc.id, pc.name FROM part_categories pc JOIN parts p ON pc.id = p.part_cat_id"
                    " WHERE (p.part_num LIKE ? OR p.name LIKE ?) ORDER BY pc.name",
                    (filter_text + "%", '%' + filter_text + '%'),
                )
            else:
                # categories that have at least one part
                cur.execute(
                    "SELECT DISTINCT pc.id, pc.name FROM part_categories pc JOIN parts p ON pc.id = p.part_cat_id"
                    " ORDER BY pc.name"
                )
            rows = cur.fetchall()
            return rows

    def get_themes(self, filter_text: str = "") -> List[Tuple[int, str]]:
        """Return list of (id, name) for themes that contain at least one set.

        If `filter_text` is provided, only themes that contain sets matching
        the filter (set_num prefix or name contains) are returned. Results are
        ordered by theme name.
        """
        with closing(create_connection(self.db_path)) as conn, conn:
            cur = conn.cursor()
            if filter_text:
                cur.execute(
                    "SELECT DISTINCT t.id, t.name FROM themes t JOIN sets s ON t.id = s.theme_id"
                    " WHERE (s.set_num LIKE ? OR s.name LIKE ?) ORDER BY t.name",
                    (filter_text + "%", '%' + filter_text + '%'),
                )
            else:
                cur.execute(
                    "SELECT DISTINCT t.id, t.name FROM themes t JOIN sets s ON t.id = s.theme_id ORDER BY t.name"
                )
            rows = cur.fetchall()
            return rows

    def list_sets(self, expanded_theme_ids: List[int], filter_text: str = "") -> Tuple[Dict[int, List[Tuple[str, str]]], bool, Dict[int, bool]]:
        """Return (sets_by_theme, overall_truncated, per_theme_truncated).

        Mirrors the behavior of `list_parts` but for sets grouped by theme.
        Only requests sets for themes included in `expanded_theme_ids`.
        """
        conn = create_connection(self.db_path)
        try:
            cur = conn.cursor()

            sets_by_theme: Dict[int, List[Tuple[str, str]]] = {}
            per_theme_truncated: Dict[int, bool] = {}

            if not expanded_theme_ids:
                return sets_by_theme, False, per_theme_truncated

            placeholders = ",".join(["?"] * len(expanded_theme_ids))
            # overall truncated flag uses same limits as parts
            if filter_text:
                truncated = False
            else:
                # check overall with 501 limit
                sql = f"SELECT set_num, name, theme_id FROM sets WHERE theme_id IN ({placeholders}) ORDER BY set_num LIMIT 501"
                cur.execute(sql, expanded_theme_ids)
                rows = cur.fetchall()
                truncated = len(rows) > 500

            for theme_id in expanded_theme_ids:
                if filter_text:
                    cur.execute(
                        "SELECT set_num, name FROM sets WHERE theme_id = ? AND (set_num LIKE ? OR name LIKE ?) ORDER BY set_num LIMIT 2000",
                        (theme_id, filter_text + "%", '%' + filter_text + '%'),
                    )
                    rows = cur.fetchall()
                    per_theme_truncated[theme_id] = False
                else:
                    cur.execute(
                        "SELECT set_num, name FROM sets WHERE theme_id = ? ORDER BY set_num LIMIT 501",
                        (theme_id,)
                    )
                    rows = cur.fetchall()
                    per_theme_truncated[theme_id] = len(rows) > 500
                    rows = rows[:500]

                sets_by_theme[theme_id] = [(sn, nm) for sn, nm in rows]

            overall_truncated = any(per_theme_truncated.values())
            return sets_by_theme, overall_truncated, per_theme_truncated
        finally:
            conn.close()

    def list_parts(self, expanded_cat_ids: List[int], filter_text: str = "") -> Tuple[object, bool]:
        """Return (rows, truncated) where truncated indicates there may be more results.

        The method preserves legacy limits (500 when unfiltered, 2000 when filtered)
        and returns a boolean flag which the view can use to show a "more" indicator.
        """
        conn = create_connection(self.db_path)
        try:
            cur = conn.cursor()

            # New grouped behavior: return a mapping category_id -> list of (part_num, name)
            # Only request parts for categories that are expanded to keep the SQL WHERE clause
            # limited (important for the global limits).
            parts_by_cat: Dict[int, List[Tuple[str, str]]] = {}
            per_cat_truncated: Dict[int, bool] = {}

            # if no expanded categories, nothing to query
            if not expanded_cat_ids:
                return parts_by_cat, False, per_cat_truncated

            # build WHERE clause for expanded categories
            placeholders = ",".join(["?"] * len(expanded_cat_ids))
            if filter_text:
                sql = f"SELECT part_num, name, part_cat_id FROM parts WHERE (part_num LIKE ? OR name LIKE ?) AND part_cat_id IN ({placeholders}) ORDER BY part_num LIMIT 2000"
                params = [filter_text + "%", '%' + filter_text + '%'] + expanded_cat_ids
                cur.execute(sql, params)
                rows = cur.fetchall()
                truncated = False
            else:
                sql = f"SELECT part_num, name, part_cat_id FROM parts WHERE part_cat_id IN ({placeholders}) ORDER BY part_num LIMIT 501"
                params = expanded_cat_ids
                cur.execute(sql, params)
                rows = cur.fetchall()
                truncated = len(rows) > 500
                rows = rows[:500]

            for cat_id in expanded_cat_ids:
                if filter_text:
                    cur.execute(
                        "SELECT part_num, name FROM parts WHERE part_cat_id = ? AND (part_num LIKE ? OR name LIKE ?) ORDER BY part_num LIMIT 2000",
                        (cat_id, filter_text + "%", '%' + filter_text + '%'),
                    )
                    rows = cur.fetchall()
                    per_cat_truncated[cat_id] = False
                else:
                    cur.execute(
                        "SELECT part_num, name FROM parts WHERE part_cat_id = ? ORDER BY part_num LIMIT 501",
                        (cat_id,)
                    )
                    rows = cur.fetchall()
                    per_cat_truncated[cat_id] = len(rows) > 500
                    rows = rows[:500]

                parts_by_cat[cat_id] = [(pn, nm) for pn, nm in rows]

            overall_truncated = any(per_cat_truncated.values())
            return parts_by_cat, overall_truncated, per_cat_truncated
        
        finally:
            conn.close()

    # --- Search debounce API ---
    def set_search_text(self, text: str):
        """Set the pending search text and schedule debounce timer.

        The search is only applied (via on_search_applied callback) after the debounce
        interval elapses. Tests may call `flush_search()` to force immediate application.
        """
        # cancel any existing timer
        if self._search_timer:
            try:
                self._search_timer.cancel()
            except Exception:
                pass
            self._search_timer = None
        self._pending_search = text
        if self._debounce_ms <= 0:
            self._apply_search()
            return
        # schedule new timer
        self._search_timer = threading.Timer(self._debounce_ms / 1000.0, self._apply_search)
        self._search_timer.daemon = True
        self._search_timer.start()

    def _apply_search(self):
        text = self._pending_search or ""
        self._pending_search = None
        self._search_timer = None
        if self._on_search_applied:
            try:
                self._on_search_applied(text)
            except Exception:
                logger.exception("Exception in on_search_applied callback")

    def flush_search(self):
        """Force immediate application of pending search (testing helper)."""
        if self._search_timer:
            try:
                self._search_timer.cancel()
            except Exception:
                pass
            self._search_timer = None
        self._apply_search()

    # --- Selection state API ---
    def select_part(self, part_num: str):
        """Set the currently selected part and notify via callback.

        The selection is represented as a tuple: ("PART", part_num).
        """
        self._selected = ("PART", part_num)
        if self._on_selection_changed:
            try:
                self._on_selection_changed(self._selected)
            except Exception:
                logger.exception("Exception in on_selection_changed (PART)")

    def select_set(self, set_num: str):
        """Set the currently selected set and notify via callback.

        The selection is represented as a tuple: ("SET", set_num).
        """
        self._selected = ("SET", set_num)
        if self._on_selection_changed:
            try:
                self._on_selection_changed(self._selected)
            except Exception:
                logger.exception("Exception in on_selection_changed (SET)")

    def get_selected(self):
        return self._selected
