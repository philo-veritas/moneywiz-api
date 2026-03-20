from abc import ABC
from dataclasses import dataclass
from decimal import Decimal
from math import isclose

from moneywiz_api.model.raw_data_handler import RawDataHandler as RDH
from moneywiz_api.model.transaction.base import Transaction, ABS_TOLERANCE
from moneywiz_api.types import ID


@dataclass
class InvestmentExchangeTransaction(Transaction):
    """
    ENT: 38
    """

    account: ID

    from_investment_holding: ID
    from_symbol: str
    to_investment_holding: ID
    to_symbol: str
    from_number_of_shares: Decimal  # neg
    to_number_of_shares: Decimal  # pos

    original_fee: Decimal  # pos: fee, neg: income?
    original_fee_currency: str

    def __init__(self, row):
        super().__init__(row)

        self.account = row["ZACCOUNT2"]
        self.from_investment_holding = row["ZFROMINVESTMENTHOLDING"]
        self.from_symbol = row["ZFROMSYMBOL"]
        self.to_investment_holding = row["ZTOINVESTMENTHOLDING"]
        self.to_symbol = row["ZTOSYMBOL"]
        self.from_number_of_shares = row["ZFROMNUMBEROFSHARES"]
        self.to_number_of_shares = row["ZTONUMBEROFSHARES"]

        self.original_fee = row["ZORIGINALFEE"]
        self.original_fee_currency = row["ZORIGINALFEECURRENCY"]

        # Fixes
        if self.original_fee_currency == self.from_symbol:
            self.from_number_of_shares += self.original_fee
        elif self.original_fee_currency == self.to_symbol:
            self.to_number_of_shares += self.original_fee

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.from_investment_holding is not None
        assert self.from_symbol
        assert self.to_investment_holding is not None
        assert self.to_symbol
        assert self.from_number_of_shares <= 0
        assert self.to_number_of_shares >= 0
        assert self.original_fee is not None
        assert self.original_fee_currency in [self.from_symbol, self.to_symbol]


@dataclass
class InvestmentTransaction(Transaction, ABC):
    """
    ENT: 39
    """

    def __init__(self, row):
        super().__init__(row)


@dataclass
class InvestmentBuyTransaction(InvestmentTransaction):
    """
    ENT: 40
    """

    account: ID
    amount: Decimal

    fee: Decimal

    investment_holding: ID
    number_of_shares: Decimal
    price_per_share: Decimal

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")

        self.fee = RDH.get_decimal(row, "ZFEE2")

        self.investment_holding = row["ZINVESTMENTHOLDING"]
        self.number_of_shares = RDH.get_decimal(row, "ZNUMBEROFSHARES1")
        self.price_per_share = RDH.get_decimal(row, "ZPRICEPERSHARE1")

        # Fixes
        self.fee = max(self.fee, 0)

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        assert self.amount <= 0
        assert self.fee is not None
        assert self.fee >= 0
        # Either tiny (close to 0) or positive
        assert isclose(float(abs(self.fee)), 0, abs_tol=ABS_TOLERANCE) or self.fee > ABS_TOLERANCE
        assert self.investment_holding is not None
        assert self.number_of_shares is not None
        assert self.number_of_shares > 0
        assert self.price_per_share is not None
        assert self.price_per_share >= 0
        assert isclose(
            float(-(self.number_of_shares * self.price_per_share + self.fee)),
            float(self.amount),
            abs_tol=ABS_TOLERANCE,
        )


@dataclass
class InvestmentSellTransaction(InvestmentTransaction):
    """
    ENT: 41
    """

    account: ID
    amount: Decimal  # neg: loss after fees, pos: income

    fee: Decimal

    investment_holding: ID
    number_of_shares: Decimal
    price_per_share: Decimal

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")

        self.fee = RDH.get_decimal(row, "ZFEE2")

        self.investment_holding = row["ZINVESTMENTHOLDING"]
        self.number_of_shares = RDH.get_decimal(row, "ZNUMBEROFSHARES1")
        self.price_per_share = RDH.get_decimal(row, "ZPRICEPERSHARE1")

        # Fixes
        self.fee = max(self.fee, 0)

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None

        assert self.fee is not None
        assert self.fee >= 0
        # Either tiny (close to 0) or positive
        assert isclose(float(abs(self.fee)), 0, abs_tol=ABS_TOLERANCE) or self.fee > ABS_TOLERANCE

        assert self.investment_holding is not None
        assert self.number_of_shares is not None
        assert self.number_of_shares > 0
        assert self.price_per_share is not None
        assert self.price_per_share >= 0
        assert isclose(
            float(self.number_of_shares * self.price_per_share - self.fee),
            float(self.amount),
            abs_tol=ABS_TOLERANCE,
        )
