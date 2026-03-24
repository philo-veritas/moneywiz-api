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


def test_get_all_returns_list():
    c1 = _make_category(1, "A")
    c2 = _make_category(2, "B")
    cm = _build_manager(c1, c2)
    result = cm.get_all()
    assert isinstance(result, list)
    assert len(result) == 2
    assert set(r.id for r in result) == {1, 2}


def test_get_all_empty():
    cm = _build_manager()
    assert cm.get_all() == []


def test_filter_with_predicate():
    c1 = _make_category(1, "餐饮")
    c2 = _make_category(2, "交通")
    c3 = _make_category(3, "餐饮外卖")
    cm = _build_manager(c1, c2, c3)
    result = cm.filter(lambda r: "餐饮" in r.name)
    assert len(result) == 2
    assert {r.id for r in result} == {1, 3}


def test_filter_no_match():
    c1 = _make_category(1, "餐饮")
    cm = _build_manager(c1)
    result = cm.filter(lambda r: r.name == "不存在")
    assert result == []


def test_find_one_returns_first_match():
    c1 = _make_category(1, "A")
    c2 = _make_category(2, "B")
    cm = _build_manager(c1, c2)
    result = cm.find_one(lambda r: r.name == "B")
    assert result is not None
    assert result.id == 2


def test_find_one_returns_none():
    c1 = _make_category(1, "A")
    cm = _build_manager(c1)
    result = cm.find_one(lambda r: r.name == "不存在")
    assert result is None


def test_count():
    c1 = _make_category(1, "A")
    c2 = _make_category(2, "B")
    cm = _build_manager(c1, c2)
    assert cm.count() == 2


def test_count_empty():
    cm = _build_manager()
    assert cm.count() == 0
