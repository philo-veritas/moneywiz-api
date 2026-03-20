from typing import Dict, Callable, List, Optional

from moneywiz_api.model import Tag
from moneywiz_api.managers.record_manager import RecordManager
from moneywiz_api.types import ID


class TagManager(RecordManager[Tag]):
    def __init__(self):
        super().__init__()

    @property
    def ents(self) -> Dict[str, Callable]:
        return {
            "Tag": Tag,
        }

    def get_by_name(self, name: str, user_id: Optional[ID] = None) -> Optional[Tag]:
        for tag in self.records().values():
            if tag.name == name:
                if user_id is None or tag.user == user_id:
                    return tag
        return None

    def search_by_name(
        self, keyword: str, user_id: Optional[ID] = None
    ) -> List[Tag]:
        keyword_lower = keyword.lower()
        results = []
        for tag in self.records().values():
            if keyword_lower in tag.name.lower():
                if user_id is None or tag.user == user_id:
                    results.append(tag)
        return results

    def get_name(self, tag_id: ID) -> str:
        tag = self.get(tag_id)
        return tag.name if tag else ""
