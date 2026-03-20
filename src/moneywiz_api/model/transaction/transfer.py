from dataclasses import dataclass
from decimal import Decimal
from math import isclose
from typing import Optional

from moneywiz_api.model.raw_data_handler import RawDataHandler as RDH
from moneywiz_api.model.transaction.base import Transaction, ABS_TOLERANCE
from moneywiz_api.types import ID


@dataclass
class TransferBudgetTransaction(Transaction):
    """
    ENT: 44
    """

    def __init__(self, row):
        super().__init__(row)
        # TODO: Not Implemented


@dataclass
class TransferDepositTransaction(Transaction):
    """
    ENT: 45
    """

    account: ID
    amount: Decimal  # pos: in

    sender_account: ID
    sender_transaction: ID

    original_amount: Decimal  # ATTENTION: sign got fixed
    original_currency: str

    sender_amount: Decimal
    sender_currency: str

    original_fee: Optional[Decimal]
    original_fee_currency: Optional[str]

    original_exchange_rate: Decimal

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")

        self.sender_account = row["ZSENDERACCOUNT"]
        self.sender_transaction = row["ZSENDERTRANSACTION"]

        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_currency = row["ZORIGINALCURRENCY"]
        self.sender_amount = RDH.get_decimal(row, "ZORIGINALSENDERAMOUNT")
        self.sender_currency = row["ZORIGINALSENDERCURRENCY"]

        self.original_fee = RDH.get_nullable_decimal(row, "ZORIGINALFEE")
        self.original_fee_currency = row["ZORIGINALFEECURRENCY"]

        self.original_exchange_rate = RDH.get_decimal(row, "ZORIGINALEXCHANGERATE")

        # Fixes
        self.original_amount = abs(self.original_amount)

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        assert self.amount > 0
        assert self.sender_account is not None
        assert self.sender_transaction is not None
        assert self.original_amount is not None
        assert self.original_amount > 0
        assert self.original_currency is not None
        assert self.sender_amount is not None
        assert self.sender_amount <= 0
        assert self.sender_currency is not None

        if self.original_fee is not None and self.original_fee != 0:
            assert self.original_fee_currency is not None

        assert self.original_exchange_rate is not None

        # original_amount could be different with amount ZCURRENCYEXCHANGERATE is playing up
        assert isclose(
            float(self.original_amount),
            float(-self.sender_amount * self.original_exchange_rate - (self.original_fee or 0)),
            abs_tol=ABS_TOLERANCE,
        )


@dataclass
class TransferWithdrawTransaction(Transaction):
    """
    ENT: 46
    """

    account: ID
    amount: Decimal  # neg: out

    recipient_account: ID
    recipient_transaction: ID

    original_amount: Decimal  # always neg
    original_currency: str

    recipient_amount: Decimal  # ATTENTION: sign got fixed
    recipient_currency: str

    original_fee: Optional[Decimal]
    original_fee_currency: Optional[str]

    original_exchange_rate: Decimal

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")

        self.recipient_account = row["ZRECIPIENTACCOUNT1"]
        self.recipient_transaction = row["ZRECIPIENTTRANSACTION"]

        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_currency = row["ZORIGINALCURRENCY"]
        self.recipient_amount = RDH.get_decimal(row, "ZORIGINALRECIPIENTAMOUNT")
        self.recipient_currency = row["ZORIGINALRECIPIENTCURRENCY"]

        self.original_fee = RDH.get_nullable_decimal(row, "ZORIGINALFEE")
        self.original_fee_currency = row["ZORIGINALFEECURRENCY"]

        self.original_exchange_rate = RDH.get_decimal(row, "ZORIGINALEXCHANGERATE")

        # Fixes
        self.recipient_amount = abs(self.recipient_amount)

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        assert self.amount < 0
        assert self.recipient_account is not None
        assert self.recipient_transaction is not None
        assert self.original_amount is not None
        assert self.original_amount < 0
        assert self.original_currency is not None
        assert self.recipient_amount is not None
        assert self.recipient_amount > 0
        assert self.recipient_currency is not None

        if self.original_fee is not None and self.original_fee != 0:
            assert self.original_fee_currency is not None

        assert self.original_exchange_rate is not None

        assert self.amount == self.original_amount
        assert isclose(
            float(self.amount),
            float(-self.recipient_amount / self.original_exchange_rate),
            abs_tol=ABS_TOLERANCE,
        )
