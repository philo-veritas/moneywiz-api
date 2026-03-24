from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

ID = int
GID = str
ENT_ID = int

CategoryType = Literal["Expenses", "Income"]


@dataclass
class CategoryAssignment:
    """一条分类分配记录：交易的某个金额部分被分配到某个分类。"""

    category_id: ID
    amount: Decimal
