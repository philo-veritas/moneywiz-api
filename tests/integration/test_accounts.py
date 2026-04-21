import pytest
from moneywiz_api.model.transaction import TransferBudgetTransaction


from conftest import (
    account_manager,
    transaction_manager,
)


@pytest.mark.parametrize(
    "account",
    list(account_manager.records().values()),
    ids=lambda account: f"{account.id}-{account.name}",
)
def test_get_all_for_account_returns_only_matching_transactions(account):
    records = transaction_manager.get_all_for_account(account.id)
    expected = sorted(
        [
            transaction
            for transaction in transaction_manager.records().values()
            if hasattr(transaction, "account")
            and transaction.account == account.id
            and not isinstance(transaction, TransferBudgetTransaction)
        ],
        key=lambda transaction: transaction.datetime,
    )

    assert [record.id for record in records] == [record.id for record in expected]
    assert all(record.account == account.id for record in records)
    assert [record.datetime for record in records] == sorted(
        record.datetime for record in records
    )


@pytest.mark.parametrize(
    "account",
    list(account_manager.records().values()),
    ids=lambda account: f"{account.id}-{account.name}",
)
def test_get_all_for_account_until_matches_manual_filter(account):
    all_records = transaction_manager.get_all_for_account(account.id)
    if not all_records:
        pytest.skip(f"Account {account.id} has no transactions")

    cutoff = all_records[len(all_records) // 2].datetime
    records = transaction_manager.get_all_for_account(account.id, until=cutoff)
    expected = [record for record in all_records if record.datetime <= cutoff]

    assert [record.id for record in records] == [record.id for record in expected]
