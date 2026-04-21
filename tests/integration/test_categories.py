import pytest

from moneywiz_api.model.transaction import (
    RefundTransaction,
    TransferDepositTransaction,
    TransferWithdrawTransaction,
    Transaction,
)
from conftest import transaction_manager, category_manager
from decimal import Decimal


def _expected_name_chain(category_id: int) -> list[str]:
    names: list[str] = []
    current = category_manager.get(category_id)
    visited: set[int] = set()
    while current is not None:
        assert current.id not in visited, f"Cycle detected for category {category_id}"
        visited.add(current.id)
        names.insert(0, current.name)
        if current.parent_id is None:
            break
        current = category_manager.get(current.parent_id)
    return names


@pytest.mark.parametrize(
    "category",
    list(category_manager.records().values()),
    ids=lambda category: f"{category.id}-{category.name}",
)
def test_category_name_chain_matches_parent_hierarchy(category):
    chain = category_manager.get_name_chain(category.id)
    assert chain == _expected_name_chain(category.id)
    assert chain[-1] == category.name


@pytest.mark.parametrize(
    "transaction",
    [
        x
        for _, x in transaction_manager.records().items()
        if isinstance(x, RefundTransaction)
    ],
)
def test_category_assignment_refund_transactions(transaction: Transaction):
    # Live DBs may legitimately omit category assignments for both the refund
    # and its original transaction; assert consistency instead of completeness.
    category_assignment = transaction_manager.category_for_transaction(transaction.id)
    original_transaction_id = (
        transaction_manager.original_transaction_for_refund_transaction(transaction.id)
    )
    assert transaction.original_transaction_id == original_transaction_id

    if original_transaction_id is None:
        assert category_assignment is None
        return

    original_transaction = transaction_manager.get(original_transaction_id)
    assert original_transaction is not None
    original_category_assignment = transaction_manager.category_for_transaction(
        original_transaction_id
    )
    assert (category_assignment is None) == (original_category_assignment is None)

    if category_assignment is None:
        return

    assert len(category_assignment) == len(original_category_assignment)

    total_amount, original_total_amount = Decimal(0), Decimal(0)

    for category, amount in category_assignment:
        total_amount += amount

    for category, amount in original_category_assignment:
        original_total_amount += amount

    if len(category_assignment) == 1:
        # total_amount == transaction.amount is not necessarily
        pass
    else:
        assert total_amount == pytest.approx(transaction.amount, abs=0.001)
    assert original_total_amount == pytest.approx(
        original_transaction.amount, abs=0.001
    )


@pytest.mark.parametrize(
    "transaction",
    [
        x
        for _, x in transaction_manager.records().items()
        if not isinstance(x, RefundTransaction)
    ],
)
def test_category_assignment_non_refund_transaction(transaction: Transaction):
    category_assignment = transaction_manager.category_for_transaction(transaction.id)
    if category_assignment:
        for category_id, _ in category_assignment:
            assert category_manager.get(category_id) is not None

        total_amount = Decimal(0)
        for category_id, amount in category_assignment:
            total_amount += amount

        if isinstance(transaction, TransferDepositTransaction) or isinstance(
            transaction, TransferWithdrawTransaction
        ):
            # The sign of the category_assignment could be wrong for Transfer Transactions
            assert abs(transaction.amount) == pytest.approx(
                abs(total_amount), abs=0.01
            ), (transaction, category_assignment)
        else:
            if all(amount == 0 for _, amount in category_assignment):
                return
            assert transaction.amount == pytest.approx(total_amount, abs=0.01), (
                transaction,
                category_assignment,
            )
