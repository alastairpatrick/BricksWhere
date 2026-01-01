from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt
import pytest
import view.main_window as mwmod

pytestmark = pytest.mark.usefixtures("app_qt")


class _DummyDirVM:
    def __init__(self, db_path, on_search_applied=None, on_selection_changed=None):
        pass

    def get_categories(self, filter_text="", only_my: bool = False):
        return []

    def get_themes(self, filter_text="", only_my: bool = False):
        return []

    def list_parts(self, expanded_list, filter_text="", only_my: bool = False):
        return ({}, False, {})

    def list_sets(self, expanded_list, filter_text="", only_my: bool = False):
        return ({}, False, {})

# patch the DirectoryViewModel in the module so MainWindow __init__ doesn't touch a DB
# Note: tests will monkeypatch `mwmod.DirectoryViewModel` to avoid DB access


def test_rebuild_grouped_section_basic(monkeypatch):
    # QApplication provided by app_qt fixture
    # patch DirectoryViewModel so MainWindow init doesn't hit the DB
    monkeypatch.setattr(mwmod, "DirectoryViewModel", _DummyDirVM)
    mw = mwmod.MainWindow(db_path=":memory:")

    tree = QTreeWidget()
    top = QTreeWidgetItem(tree, ["Top"])

    groups = [(1, "G1"), (2, "G2")]
    expanded_ids = {1}

    def list_fetcher(expanded_list, filter_text=""):
        items_by_group = {}
        per_group_truncated = {}
        if 1 in expanded_list:
            items_by_group[1] = [("a", "Alpha")]
            per_group_truncated[1] = False
        return items_by_group, False, per_group_truncated

    overall = mw._rebuild_grouped_section(top, groups, expanded_ids, list_fetcher)
    assert overall is False
    assert top.childCount() == 2

    # find G1 and verify it contains the fetched child
    g1 = None
    for i in range(top.childCount()):
        if top.child(i).text(0) == "G1":
            g1 = top.child(i)
            break
    assert g1 is not None
    # one real child (plus placeholder removed)
    assert g1.childCount() == 1
    child = g1.child(0)
    assert child.text(0) == "a - Alpha"
    assert child.data(0, Qt.UserRole) == "a"


def test_rebuild_grouped_section_truncation(monkeypatch):
    # QApplication provided by app_qt fixture
    monkeypatch.setattr(mwmod, "DirectoryViewModel", _DummyDirVM)
    mw = mwmod.MainWindow(db_path=":memory:")

    tree = QTreeWidget()
    top = QTreeWidgetItem(tree, ["Top"])

    groups = [(10, "Big")]
    expanded_ids = {10}

    def list_fetcher(expanded_list, filter_text=""):
        items_by_group = {}
        per_group_truncated = {}
        if 10 in expanded_list:
            items_by_group[10] = [("b", "Beta")]
            per_group_truncated[10] = True
        return items_by_group, True, per_group_truncated

    overall = mw._rebuild_grouped_section(top, groups, expanded_ids, list_fetcher)
    assert overall is True

    g = top.child(0)
    # should contain one item + truncation indicator
    assert g.childCount() == 2
    assert g.child(0).text(0) == "b - Beta"
    assert g.child(0).data(0, Qt.UserRole) == "b"
    assert "showing first 500" in g.child(1).text(0)
