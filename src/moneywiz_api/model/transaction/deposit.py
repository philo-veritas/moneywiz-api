from dataclasses import dataclass
from decimal import Decimal
from math import isclose
from typing import Optional

from moneywiz_api.model.raw_data_handler import RawDataHandler as RDH
from moneywiz_api.model.transaction.base import Transaction, ABS_TOLERANCE
from moneywiz_api.types import ID


@dataclass
class DepositTransaction(Transaction):
    """
    ENT: 37
    """

    account: ID
    amount: Decimal  # neg: expense, pos: income
    payee: Optional[ID]

    # FX
    original_currency: str
    original_amount: Decimal  # neg: expense, pos: income
    original_exchange_rate: Optional[Decimal]

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")
        self.payee = row["ZPAYEE2"]
        self.original_currency = row["ZORIGINALCURRENCY"]
        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_exchange_rate = RDH.get_nullable_decimal(
            row, "ZORIGINALEXCHANGERATE"
        )

        # Fixes
        if self.original_exchange_rate == Decimal(0):
            self.original_exchange_rate = None

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None, self.as_dict()
        assert self.amount is not None, self.as_dict()
        # self.payee can be None
        assert self.original_currency is not None, self.as_dict()
        assert self.original_amount is not None, self.as_dict()

        assert self.amount * self.original_amount > 0, self.as_dict()  # Same sign
        if self.original_exchange_rate is not None:
            assert isclose(
                float(self.amount),
                float(self.original_amount * self.original_exchange_rate),
                abs_tol=ABS_TOLERANCE,
            ), self.as_dict()


@dataclass
class WithdrawTransaction(Transaction):
    """
    ENT: 47
    """

    account: ID
    amount: Decimal  # neg: expense, pos: income
    payee: Optional[ID]

    # FX
    original_currency: str
    original_amount: Decimal  # neg: expense, pos: income ATTENTION: sign got fixed
    original_exchange_rate: Optional[Decimal]

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")
        self.payee = row["ZPAYEE2"]

        self.original_currency = row["ZORIGINALCURRENCY"]
        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_exchange_rate = RDH.get_nullable_decimal(
            row, "ZORIGINALEXCHANGERATE"
        )

        # Fixes
        if self.amount * self.original_amount < 0:
            self.original_amount = -self.original_amount

        if self.original_exchange_rate == Decimal(0):
            self.original_exchange_rate = None

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        # self.payee can be None
        assert self.original_currency is not None
        assert self.original_amount is not None

        assert self.amount * self.original_amount > 0

        if self.original_exchange_rate is not None:
            assert isclose(
                float(self.amount),
                float(self.original_amount * self.original_exchange_rate),
                abs_tol=ABS_TOLERANCE,
            )


@dataclass
class RefundTransaction(Transaction):
    """
    ENT: 43
    """

    account: ID
    amount: Decimal
    payee: Optional[ID]

    # FX
    original_currency: str
    original_amount: Decimal
    original_exchange_rate: Optional[Decimal]

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")
        self.payee = row["ZPAYEE2"]

        self.original_currency = row["ZORIGINALCURRENCY"]
        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_exchange_rate = RDH.get_nullable_decimal(
            row, "ZORIGINALEXCHANGERATE"
        )

        # Fixes
        if self.original_exchange_rate == Decimal(0):
            self.original_exchange_rate = None

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        assert self.amount > 0

        assert self.original_currency is not None
        assert self.original_amount is not None
        assert self.original_amount > 0

        if self.original_exchange_rate is not None:
            assert isclose(
                float(self.amount),
                float(self.original_amount * self.original_exchange_rate),
                abs_tol=ABS_TOLERANCE,
            )
