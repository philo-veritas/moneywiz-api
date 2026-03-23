from typing import Dict, Callable, List, Set

from moneywiz_api.model.category import Category
from moneywiz_api.managers.record_manager import RecordManager
from moneywiz_api.types import ID, GID


class CategoryManager(RecordManager[Category]):
    def __init__(self):
        super().__init__()

    @property
    def ents(self) -> Dict[str, Callable]:
        return {
            "Category": Category,
        }

    def get_name_chain(self, category_id: ID) -> List[str]:
        ret: List[str] = []
        current = self.get(category_id)
        while current:
            ret.insert(0, current.name)
            if not current.parent_id:
                break
            else:
                current = self.get(current.parent_id)
        return ret

    def get_name_chain_by_gid(self, category_gid: GID) -> List[str]:
        current = self.get_by_gid(category_gid)
        return self.get_name_chain(current.id)

    def get_categories_for_user(self, user_id: ID) -> List[Category]:
        return sorted(
            [x for _, x in self.records().items() if x.user == user_id],
            key=lambda x: x.type,
        )

    def get_by_name(self, name: str, user_id: ID | None = None) -> List[Category]:
        results = []
        for cat in self.records().values():
            if cat.name == name:
                if user_id is None or cat.user == user_id:
                    results.append(cat)
        return results

    def search_by_name(self, keyword: str, user_id: ID | None = None) -> List[Category]:
        keyword_lower = keyword.lower()
        results = []
        for cat in self.records().values():
            if keyword_lower in cat.name.lower():
                if user_id is None or cat.user == user_id:
                    results.append(cat)
        return results

    def get_children(self, category_id: ID) -> List[Category]:
        return [cat for cat in self.records().values() if cat.parent_id == category_id]

    def get_subtree_ids(self, category_id: ID) -> Set[ID]:
        result: Set[ID] = {category_id}
        queue = [category_id]
        while queue:
            current = queue.pop()
            for child in self.get_children(current):
                if child.id not in result:
                    result.add(child.id)
                    queue.append(child.id)
        return result
