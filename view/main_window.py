import os
import queue
import logging
import traceback
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QMainWindow,
    QDockWidget,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QSpinBox,
    QLabel,
    QScrollArea,
    QLineEdit as QLineEditWidget,
    QHBoxLayout,
)
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtCore import Signal, Qt, QTimer

logger = logging.getLogger(__name__)

from .sync_progress_dialog import SyncProgressDialog
from viewmodel import DirectoryViewModel, MainViewModel, SyncViewModel


class MainWindow(QMainWindow):
    # emitted when a sync dialog is created; test hook for deterministic tests
    dialog_created = Signal(object)

    def __init__(self, db_path: str = "data.db"):
        super().__init__()
        self.setWindowTitle("BricksWhere")
        self._db_path = db_path

        # Simple central UI
        central = QWidget()
        layout = QVBoxLayout(central)
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        layout.addWidget(self._detail)
        # area for displaying element images and color names
        self._images_area = QScrollArea()
        self._images_area.setWidgetResizable(True)
        self._images_widget = QWidget()
        self._images_layout = QVBoxLayout(self._images_widget)
        self._images_area.setWidget(self._images_widget)
        layout.addWidget(self._images_area)
        self.setCentralWidget(central)

        # Menu -> Tools -> Resynchronize with Rebrickable
        tools = self.menuBar().addMenu("Tools")
        self.sync_action = QAction("Resynchronize with Rebrickable", self)
        self.sync_action.triggered.connect(self.start_sync)
        tools.addAction(self.sync_action)

        # Directory (left)
        dock = QDockWidget("Directory", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock_widget = QWidget()
        dock_layout = QVBoxLayout(dock_widget)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search part number or name...")
        # Delegate debounce and application of search text to the DirectoryViewModel
        self._search.textChanged.connect(self._on_search_text_changed)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

        dock_layout.addWidget(self._search)
        dock_layout.addWidget(self._tree)
        dock.setWidget(dock_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        # create top-level nodes
        self._parts_node = QTreeWidgetItem(self._tree, ["Parts"])
        self._sets_node = QTreeWidgetItem(self._tree, ["Sets"])
        self._tree.addTopLevelItem(self._parts_node)
        self._tree.addTopLevelItem(self._sets_node)

        # respond to expansions/collapses so we only request parts for expanded categories
        self._tree.itemExpanded.connect(lambda it: self._populate_parts(filter_text=self._search.text()))
        self._tree.itemCollapsed.connect(lambda it: self._populate_parts(filter_text=self._search.text()))

        # view-models
        # directory VM receives callbacks from the view-model to update the view
        self._directory_vm = DirectoryViewModel(self._db_path, on_search_applied=self._on_search_applied, on_selection_changed=self._on_vm_selection_changed)
        self._main_vm = MainViewModel(self._db_path)
        self._sync_vm = SyncViewModel(self._db_path)

        from .image_loader import BackgroundImageFetcher
        self._img_fetcher = BackgroundImageFetcher(self._db_path)

        # image fetcher timer
        self._img_poll_timer = QTimer(self)
        self._img_poll_timer.setInterval(100)
        self._img_poll_timer.timeout.connect(self._poll_img_queue)

        # populate initial parts list
        self._populate_parts()

    def start_sync(self):
        self.sync_action.setEnabled(False)

        # start sync via view-model; it will create its own queue & cancel event
        progress_q = self._sync_vm.start_async()

        # create and show modal progress dialog which will poll the queue and
        # instruct the view-model to cancel when the user clicks Cancel
        dlg = SyncProgressDialog(self._sync_vm, parent=self)
        # notify listeners/tests that the dialog was created
        try:
            self.dialog_created.emit(dlg)
        except Exception:
            pass

        # run modal dialog; it will close (switch to OK) when sync finishes
        dlg.exec()

        # ensure sync thread is finished before refreshing UI
        self._sync_vm.join()

        # refresh parts list after sync completes (success, failure, or cancel)
        try:
            self._populate_parts()
        except Exception:
            # ignore errors while refreshing UI to avoid crashing the app
            pass

        # re-enable action after dialog closes
        self.sync_action.setEnabled(True)

    def _on_search_text_changed(self, text: str):
        # delegate debounce and eventual application to the view-model
        self._directory_vm.set_search_text(text)

    def _on_search_applied(self, text: str):
        # called by DirectoryViewModel when the debounced search is applied
        self._populate_parts(filter_text=text)

    def _rebuild_grouped_section(self, top_node, groups, expanded_ids, list_fetcher, *, group_data_role=Qt.UserRole+1, item_data_role=Qt.UserRole, item_text_fmt=None, filter_text=""):
        """Helper to populate a top-level `top_node` with grouped children.

        - `groups` is a list of (id, name) tuples for group nodes.
        - `expanded_ids` is a set of group ids that should be expanded.
        - `list_fetcher` is a callable(expanded_list, filter_text) -> (items_by_group, overall_truncated, per_group_truncated)
        - `group_data_role` and `item_data_role` control where ids are stored.
        - `item_text_fmt` is a callable(key,name)->text (defaults to "{key} - {name}").
        Returns overall_truncated boolean from the list_fetcher.
        """
        if item_text_fmt is None:
            item_text_fmt = lambda k, n: f"{k} - {n}"

        # clear existing children for this section and create group nodes
        top_node.takeChildren()
        group_nodes = {}
        for gid, gname in groups:
            node = QTreeWidgetItem(top_node, [gname])
            node.setData(0, group_data_role, gid)
            node.setExpanded(gid in expanded_ids)
            placeholder = QTreeWidgetItem(node, ["..."])
            placeholder.setDisabled(True)
            group_nodes[gid] = node

        # request items only for expanded groups
        expanded_list = list(expanded_ids)
        items_by_group, overall_truncated, per_group_truncated = list_fetcher(expanded_list, filter_text=filter_text)

        for gid, items in items_by_group.items():
            node = group_nodes.get(gid)
            if not node:
                continue
            node.takeChildren()
            for key, name in items:
                item = QTreeWidgetItem(node, [item_text_fmt(key, name)])
                item.setData(0, item_data_role, key)
            if per_group_truncated.get(gid):
                more = QTreeWidgetItem(node, ["... (showing first 500 results)"])
                more.setDisabled(True)

        return overall_truncated

    def _collect_expanded_ids(self, parent_node, role=Qt.UserRole+1):
        """Return set of ids for children of `parent_node` that are expanded.

        The id is read from `child.data(0, role)`. Swallows errors during access.
        """
        ids = set()
        for i in range(parent_node.childCount()):
            child = parent_node.child(i)
            try:
                gid = child.data(0, role)
            except Exception:
                gid = None
            if gid is not None and child.isExpanded():
                ids.add(gid)
        return ids

    def _populate_parts(self, filter_text: str = ""):
        # Preserve which categories and theme nodes are expanded before rebuild
        expanded_ids = self._collect_expanded_ids(self._parts_node, role=Qt.UserRole + 1)
        expanded_theme_ids = self._collect_expanded_ids(self._sets_node, role=Qt.UserRole + 1)

        # Clear existing children under parts node and recreate category nodes
        # Block tree signals while we programmatically rebuild nodes to avoid
        # recursive calls to _populate_parts via the expansion/collapse handlers.
        self._tree.blockSignals(True)
        try:
            # rebuild Parts section
            categories = self._directory_vm.get_categories(filter_text)
            _ = self._rebuild_grouped_section(self._parts_node, categories, expanded_ids, self._directory_vm.list_parts, group_data_role=Qt.UserRole+1, item_data_role=Qt.UserRole, item_text_fmt=lambda k, n: f"{k} - {n}", filter_text=filter_text)

            # rebuild Sets/Themes section
            themes = self._directory_vm.get_themes(filter_text)
            _ = self._rebuild_grouped_section(self._sets_node, themes, expanded_theme_ids, self._directory_vm.list_sets, group_data_role=Qt.UserRole+1, item_data_role=Qt.UserRole + 2, item_text_fmt=lambda k, n: f"{k} - {n}", filter_text=filter_text)
        finally:
            self._tree.blockSignals(False)

    def _on_tree_selection_changed(self):
        items = self._tree.selectedItems()
        if not items:
            return
        item = items[0]
        # support both part and set selections
        part_num = item.data(0, Qt.UserRole)
        if part_num:
            self._directory_vm.select_part(part_num)
            return
        set_num = item.data(0, Qt.UserRole + 2)
        if set_num:
            self._directory_vm.select_set(set_num)
            return

    def _on_vm_selection_changed(self, selection):
        # view-model informs us that the selection changed; selection is a tuple
        # like ("PART", part_num) or ("SET", set_num)
        if not selection or not isinstance(selection, tuple) or len(selection) != 2:
            return
        kind, key = selection
        # clear existing image/widgets area before updating for new selection
        for i in reversed(range(self._images_layout.count())):
            w = self._images_layout.takeAt(i).widget()
            if w:
                w.setParent(None)

        if kind == "PART":
            info = self._main_vm.get_part_detail(key)
            if not info:
                return
            colors = info.get("colors", [])
            text = f"Part: {info['part_num']}\nName: {info['name']}"
            # include totals if available
            counts = info.get("counts")
            if counts:
                tp = counts.get("total_pieces", 0)
                te = counts.get("total_elements", 0)
                text += f"\n\nCollection: {tp} piece(s) across {te} element(s)"
            self._detail.setPlainText(text)
            elements = info.get("elements", [])
        elif kind == "SET":
            info = self._main_vm.get_set_detail(key)
            if not info:
                return
            text = f"Set: {info['set_num']}\nName: {info['name']}"
            self._detail.setPlainText(text)
            # represent the set image as a single element for the image fetcher
            elements = [{"color": info.get("name", ""), "img_url": info.get("img_url", "")}]
            logger.debug("selection SET %s, img_url=%s", key, elements[0]['img_url'])
            # show editable user fields (quantity and remark)
            user = self._main_vm.get_user_set(key)

            # quantity row
            qty_row = QWidget()
            qty_layout = QHBoxLayout(qty_row)
            qty_label = QLabel("Quantity:")
            qty_spin = QSpinBox()
            qty_spin.setMinimum(0)
            qty_spin.setMaximum(999999)
            qty_spin.setValue(user.get("quantity", 0))
            qty_layout.addWidget(qty_label)
            qty_layout.addWidget(qty_spin)
            self._images_layout.addWidget(qty_row)

            # remark row
            rem_row = QWidget()
            rem_layout = QHBoxLayout(rem_row)
            rem_label = QLabel("Remark:")
            rem_edit = QLineEditWidget()
            rem_edit.setText(user.get("remark", ""))
            rem_layout.addWidget(rem_label)
            rem_layout.addWidget(rem_edit)
            self._images_layout.addWidget(rem_row)

            # handler to persist changes when user sets non-defaults
            def _persist():
                q = qty_spin.value()
                r = rem_edit.text()
                # only create/update when something other than defaults
                if q != 0 or (r and r != ""):
                    try:
                        self._main_vm.set_user_set(key, q, r)
                    except Exception:
                        logger.exception("Failed to persist user_set %s", key)

            qty_spin.valueChanged.connect(lambda v: _persist())
            rem_edit.textChanged.connect(lambda t: _persist())
        else:
            return

        fetch_images = []
        for element in elements:
            color = element["color"]
            row = QWidget()
            row_layout = QHBoxLayout(row)
            img_label = QLabel()
            img_label.setFixedSize(64, 64)
            name_label = QLabel(color)
            # show per-color count if present
            count = element.get("count")
            if count is None:
                count_text = ""
            else:
                count_text = f"{count} pcs"
            count_label = QLabel(count_text)
            row_layout.addWidget(img_label)
            row_layout.addWidget(name_label)
            row_layout.addWidget(count_label)
            self._images_layout.addWidget(row)
            fetch_images.append({"tag": img_label, "img_url": element["img_url"]})

        # cancel any running fetcher for the previous selection
        self._img_fetcher.cancel()
        self._img_fetcher.join()

        # start background fetcher
        self._img_queue = self._img_fetcher.start(fetch_images)
        logger.debug("BackgroundImageFetcher.start returned queue")

        # start polling
        self._img_poll_timer.start()

    def _poll_img_queue(self):
        try:
            while True:
                item = self._img_queue.get_nowait()
                if item == "ALL_DONE":
                    self._img_poll_timer.stop()
                    break
                img_label, img_bytes = item
                logger.debug("fetched image bytes=%s", None if img_bytes is None else len(img_bytes))
                if img_bytes:
                    pix = QPixmap()
                    pix.loadFromData(img_bytes)
                    img_label.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except queue.Empty:
            pass
