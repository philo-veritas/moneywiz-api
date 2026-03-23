from typing import Dict, Callable, List, Optional

from moneywiz_api.model.payee import Payee
from moneywiz_api.managers.record_manager import RecordManager
from moneywiz_api.types import ID


class PayeeManager(RecordManager[Payee]):
    def __init__(self):
        super().__init__()

    @property
    def ents(self) -> Dict[str, Callable]:
        return {
            "Payee": Payee,
        }

    def get_by_name(self, name: str, user_id: Optional[ID] = None) -> Optional[Payee]:
        for payee in self.records().values():
            if payee.name == name:
                if user_id is None or payee.user == user_id:
                    return payee
        return None

    def search_by_name(self, keyword: str, user_id: Optional[ID] = None) -> List[Payee]:
        keyword_lower = keyword.lower()
        results = []
        for payee in self.records().values():
            if keyword_lower in payee.name.lower():
                if user_id is None or payee.user == user_id:
                    results.append(payee)
        return results

    def get_name(self, payee_id: ID) -> str:
        payee = self.get(payee_id)
        return payee.name if payee else ""
