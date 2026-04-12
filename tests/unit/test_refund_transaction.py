from datetime import datetime

from moneywiz_api.model.transaction import RefundTransaction
from moneywiz_api.utils import get_date


def _make_refund_row():
    created_at = datetime(2024, 1, 1, 9, 0, 0)
    txn_at = datetime(2024, 1, 2, 10, 30, 0)
    return {
        "Z_PK": 1,
        "Z_ENT": 43,
        "ZGID": "refund-gid-1",
        "ZOBJECTCREATIONDATE": get_date(created_at),
        "ZRECONCILED": 1,
        "ZAMOUNT1": 12.34,
        "ZDESC2": "Refund",
        "ZDATE1": get_date(txn_at),
        "ZNOTES1": None,
        "ZACCOUNT2": 10,
        "ZPAYEE2": 20,
        "ZORIGINALCURRENCY": "USD",
        "ZORIGINALAMOUNT": 12.34,
        "ZORIGINALEXCHANGERATE": 1.0,
    }


def test_refund_transaction_to_dict_includes_original_transaction_id():
    refund = RefundTransaction(_make_refund_row())
    refund.original_transaction_id = 99
    data = refund.to_dict()
    assert data["original_transaction_id"] == 99
