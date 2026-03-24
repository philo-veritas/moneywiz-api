from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from moneywiz_api.model.raw_data_handler import RawDataHandler as RDH
from moneywiz_api.model.record import Record
from moneywiz_api.types import ID, CategoryAssignment

ABS_TOLERANCE = 0.001


@dataclass
class Transaction(Record, ABC):
    """
    ENT: 36
    """

    reconciled: bool

    amount: Decimal
    description: str
    datetime: datetime
    notes: Optional[str]

    _category_assignments: List[CategoryAssignment] = field(
        default_factory=list, init=False, repr=False
    )

    def __init__(self, row):
        super().__init__(row)
        self.reconciled = row["ZRECONCILED"] == 1
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")
        self.description = row["ZDESC2"]
        self.datetime = RDH.get_datetime(row, "ZDATE1")
        self.notes = row["ZNOTES1"]
        self._category_assignments = []

        # Fixes

        # Validate
        assert self.reconciled is not None, self.as_dict()
        assert self.amount is not None, self.as_dict()
        assert self.description is not None, self.as_dict()
        assert self.datetime is not None, self.as_dict()
        # self.notes can be None

    @property
    def categories(self) -> List[CategoryAssignment]:
        """该交易的所有分类分配。"""
        return self._category_assignments

    @property
    def category_id(self) -> Optional[ID]:
        """首个分类 ID，无分类返回 None（大部分交易只有一个分类）。"""
        if self._category_assignments:
            return self._category_assignments[0].category_id
        return None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["categories"] = [
            {"category_id": ca.category_id, "amount": float(ca.amount)}
            for ca in self._category_assignments
        ]
        return result
