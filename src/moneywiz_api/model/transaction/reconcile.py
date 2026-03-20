from dataclasses import dataclass
from decimal import Decimal

from moneywiz_api.model.raw_data_handler import RawDataHandler as RDH
from moneywiz_api.model.transaction.base import Transaction
from moneywiz_api.types import ID


@dataclass
class ReconcileTransaction(Transaction):
    """
    ENT: 42
    """

    account: ID

    reconcile_amount: Decimal | None  # new balance
    reconcile_number_of_shares: Decimal | None  # new balance

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.reconcile_amount = RDH.get_nullable_decimal(row, "ZRECONCILEAMOUNT")
        self.reconcile_number_of_shares = RDH.get_nullable_decimal(
            row, "ZRECONCILENUMBEROFSHARES"
        )

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert (
            self.reconcile_amount is not None
            or self.reconcile_number_of_shares is not None
        )
