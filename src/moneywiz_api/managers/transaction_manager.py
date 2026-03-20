from datetime import datetime
from typing import Dict, Callable, List, Optional, Set, Tuple
from decimal import Decimal

from moneywiz_api.database_accessor import DatabaseAccessor
from moneywiz_api.model.transaction import (
    Transaction,
    DepositTransaction,
    InvestmentExchangeTransaction,
    InvestmentBuyTransaction,
    InvestmentSellTransaction,
    ReconcileTransaction,
    RefundTransaction,
    TransferBudgetTransaction,
    TransferDepositTransaction,
    TransferWithdrawTransaction,
    WithdrawTransaction,
)
from moneywiz_api.managers.record_manager import RecordManager
from moneywiz_api.types import ID


class TransactionManager(RecordManager[Transaction]):
    def __init__(self):
        super().__init__()
        self.category_assignment: Dict[ID, List[Tuple[ID, Decimal]]] = {}
        self.refund_maps: Dict[ID, ID] = {}
        self.tags_map: Dict[ID, ID] = {}
        self._category_to_transactions: Dict[ID, Set[ID]] = {}

    @property
    def ents(self) -> Dict[str, Callable]:
        return {
            "DepositTransaction": DepositTransaction,
            "InvestmentExchangeTransaction": InvestmentExchangeTransaction,
            "InvestmentBuyTransaction": InvestmentBuyTransaction,
            "InvestmentSellTransaction": InvestmentSellTransaction,
            "ReconcileTransaction": ReconcileTransaction,
            "RefundTransaction": RefundTransaction,
            "TransferBudgetTransaction": TransferBudgetTransaction,
            "TransferDepositTransaction": TransferDepositTransaction,
            "TransferWithdrawTransaction": TransferWithdrawTransaction,
            "WithdrawTransaction": WithdrawTransaction,
        }

    def load(self, db_accessor: DatabaseAccessor) -> None:
        super().load(db_accessor)
        self.category_assignment: Dict[ID, List[Tuple[ID, Decimal]]] = (
            db_accessor.get_category_assignment()
        )
        self.refund_maps: Dict[ID, ID] = db_accessor.get_refund_maps()
        self.tags_map: Dict[ID, ID] = db_accessor.get_tags_map()
        self._build_category_index()

    def _build_category_index(self) -> None:
        self._category_to_transactions.clear()
        for txn_id, cats in self.category_assignment.items():
            for cat_id, _ in cats:
                self._category_to_transactions.setdefault(cat_id, set()).add(txn_id)

    def category_for_transaction(
        self, transaction_id: ID
    ) -> List[Tuple[ID, Decimal]] | None:
        return self.category_assignment.get(transaction_id)

    def tags_for_transaction(self, transaction_id: ID) -> List[ID] | None:
        return self.tags_map.get(transaction_id)

    def original_transaction_for_refund_transaction(
        self, transaction_id: ID
    ) -> ID | None:
        return self.refund_maps.get(transaction_id)

    def _filter(
        self,
        transactions: List[Transaction],
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Transaction]:
        result = []
        for t in transactions:
            if isinstance(t, TransferBudgetTransaction):
                continue
            if since and t.datetime < since:
                continue
            if until and t.datetime > until:
                continue
            result.append(t)
        result.sort(key=lambda x: x.datetime)
        return result

    def get_all_for_account(
        self,
        account_id: ID,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Transaction]:
        txns = [
            t
            for t in self.records().values()
            if hasattr(t, "account") and t.account == account_id
        ]
        return self._filter(txns, since=since, until=until)

    def get_all(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Transaction]:
        return self._filter(list(self.records().values()), since=since, until=until)

    def get_uncategorized(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Transaction]:
        all_records = self.records()
        txns = [
            t
            for tid, t in all_records.items()
            if tid not in self.category_assignment
        ]
        return self._filter(txns, since=since, until=until)

    def get_by_category(
        self,
        category_ids: ID | List[ID],
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Transaction]:
        if isinstance(category_ids, int):
            category_ids = [category_ids]
        txn_ids: Set[ID] = set()
        for cat_id in category_ids:
            txn_ids |= self._category_to_transactions.get(cat_id, set())
        all_records = self.records()
        txns = [all_records[tid] for tid in txn_ids if tid in all_records]
        return self._filter(txns, since=since, until=until)
