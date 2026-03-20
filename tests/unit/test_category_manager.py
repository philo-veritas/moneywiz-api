from unittest.mock import MagicMock

from moneywiz_api.managers.category_manager import CategoryManager


def _make_category(id, name, parent_id=None, user=1):
    cat = MagicMock()
    cat.id = id
    cat.name = name
    cat.parent_id = parent_id
    cat.user = user
    cat.type = "Expenses"
    cat.gid = f"gid-{id}"
    return cat


def _build_manager(*categories):
    cm = CategoryManager.__new__(CategoryManager)
    cm._records = {c.id: c for c in categories}
    cm._gid_to_id = {c.gid: c.id for c in categories}
    return cm


def test_get_subtree_ids_single():
    root = _make_category(1, "Root")
    cm = _build_manager(root)
    assert cm.get_subtree_ids(1) == {1}


def test_get_subtree_ids_tree():
    root = _make_category(1, "Root")
    child1 = _make_category(2, "Child1", parent_id=1)
    child2 = _make_category(3, "Child2", parent_id=1)
    grandchild = _make_category(4, "Grandchild", parent_id=2)
    cm = _build_manager(root, child1, child2, grandchild)
    assert cm.get_subtree_ids(1) == {1, 2, 3, 4}


def test_get_subtree_ids_leaf():
    root = _make_category(1, "Root")
    child = _make_category(2, "Child", parent_id=1)
    cm = _build_manager(root, child)
    assert cm.get_subtree_ids(2) == {2}


def test_get_children():
    root = _make_category(1, "Root")
    child1 = _make_category(2, "Child1", parent_id=1)
    child2 = _make_category(3, "Child2", parent_id=1)
    other = _make_category(4, "Other", parent_id=2)
    cm = _build_manager(root, child1, child2, other)
    children = cm.get_children(1)
    assert {c.id for c in children} == {2, 3}
