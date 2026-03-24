# moneywiz-api 接口参考文档

> 本文档面向人工阅读和 AI Agent 调用，覆盖所有公开接口、字段定义与使用示例。

---

## 目录

1. [概览](#1-概览)
2. [安装与快速上手](#2-安装与快速上手)
3. [核心类型定义](#3-核心类型定义)
4. [MoneywizApi 门面类](#4-moneywizapi-门面类)
5. [Manager 参考](#5-manager-参考)
   - [RecordManager 基类（通用方法）](#51-recordmanager-基类)
   - [AccountManager](#52-accountmanager)
   - [CategoryManager](#53-categorymanager)
   - [TransactionManager](#54-transactionmanager)
   - [PayeeManager](#55-payeemanager)
   - [TagManager](#56-tagmanager)
   - [InvestmentHoldingManager](#57-investmentholdingmanager)
6. [数据模型参考](#6-数据模型参考)
   - [Record 基类](#61-record-基类)
   - [Account 及子类](#62-account-及子类)
   - [Transaction 及子类](#63-transaction-及子类)
   - [Category](#64-category)
   - [Payee](#65-payee)
   - [Tag](#66-tag)
   - [InvestmentHolding](#67-investmentholding)
7. [CLI 参考](#7-cli-参考)
8. [常用查询模式](#8-常用查询模式)
9. [AI Agent 调用指引](#9-ai-agent-调用指引)

---

## 1. 概览

moneywiz-api 是一个**只读** Python 库，用于访问 MoneyWiz 个人理财应用的 SQLite 数据库。

**数据流架构：**

```
SQLite DB
    └── DatabaseAccessor          # 直接操作 SQLite，映射 Z_ENT → 类型名
            └── RecordManager[T]  # 泛型基类，自动加载/索引/查询
                    ├── AccountManager
                    ├── CategoryManager
                    ├── TransactionManager
                    ├── PayeeManager
                    ├── TagManager
                    └── InvestmentHoldingManager
                            └── Model (dataclass)   # 强类型数据对象
                                    └── MoneywizApi # 门面，统一入口
                                            └── CLI / ShellHelper / 用户代码
```

**关键约定：**

- 所有数据模型为不可变 dataclass，库设计为只读，不提供写入接口
- SQLite 中所有实体存储在 `ZSYNCOBJECT` 单表，通过 `Z_ENT` 区分类型
- 时间戳为相对 2001-01-01（Core Data epoch）的 float 秒数，库内自动转换为 `datetime`
- 金额为 float 存储，库内转换为 `Decimal` 保证精度
- `amount` 字段符号约定：**负数 = 支出/转出，正数 = 收入/转入**

---

## 2. 安装与快速上手

```bash
pip install moneywiz-db-api
# 或使用 uv
uv add moneywiz-db-api
```

**最小可用示例：**

```python
from pathlib import Path
from moneywiz_api import MoneywizApi

DB_PATH = Path("~/Library/Containers/com.moneywiz.personalfinance"
               "/Data/Documents/.AppData/ipadMoneyWiz.sqlite").expanduser()

# 推荐使用上下文管理器，自动关闭数据库连接
with MoneywizApi(DB_PATH) as api:
    # 获取所有交易（按时间升序，排除预算转账）
    transactions = api.transaction_manager.get_all()

    # 获取所有分类
    categories = api.category_manager.get_all()

    # 获取未分类交易
    uncategorized = api.transaction_manager.get_uncategorized()

    # 获取账户列表（某用户）
    accounts = api.account_manager.get_accounts_for_user(user_id=2)
```

---

## 3. 核心类型定义

**文件：** `src/moneywiz_api/types.py`

```python
ID = int                  # 主键 (Z_PK)
GID = str                 # 全局唯一 ID (ZGID)
ENT_ID = int              # 实体类型 ID (Z_ENT)
CategoryType = Literal["Expenses", "Income"]  # 分类类型

@dataclass
class CategoryAssignment:
    """交易的单条分类分配记录。"""
    category_id: ID      # 分类主键
    amount: Decimal      # 该分类对应的金额
```

---

## 4. MoneywizApi 门面类

**文件：** `src/moneywiz_api/moneywiz_api.py`

**导入：**

```python
from moneywiz_api import MoneywizApi
```

### 构造函数

```python
MoneywizApi(db_file: Path)
```

- `db_file`：MoneyWiz SQLite 数据库文件路径（必填）
- 构造时自动调用 `load()`，加载所有 Manager 数据

macOS 默认路径：
```
~/Library/Containers/com.moneywiz.personalfinance/Data/Documents/.AppData/ipadMoneyWiz.sqlite
```

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `accessor` | `DatabaseAccessor` | SQLite 数据库访问器（底层接口） |
| `account_manager` | `AccountManager` | 账户管理器 |
| `payee_manager` | `PayeeManager` | 收款人管理器 |
| `category_manager` | `CategoryManager` | 分类管理器 |
| `transaction_manager` | `TransactionManager` | 交易管理器 |
| `investment_holding_manager` | `InvestmentHoldingManager` | 投资持仓管理器 |
| `tag_manager` | `TagManager` | 标签管理器 |

### 方法

| 方法 | 说明 |
|------|------|
| `load() -> None` | 重新加载所有 Manager 数据（构造时自动调用） |
| `__enter__() -> MoneywizApi` | 支持 `with` 语句 |
| `__exit__(...) -> False` | 退出时关闭数据库连接 |

### 上下文管理器用法

```python
with MoneywizApi(db_path) as api:
    result = api.transaction_manager.get_all()
# 退出 with 块后自动关闭数据库连接
```

---

## 5. Manager 参考

所有 Manager 都继承 `RecordManager[T]` 泛型基类，并扩展了各自的专属方法。

### 5.1 RecordManager 基类

**文件：** `src/moneywiz_api/managers/record_manager.py`

以下方法在**所有 Manager** 中均可用：

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get` | `(record_id: ID) -> T \| None` | 单条记录或 `None` | 按主键查找 |
| `get_by_gid` | `(gid: GID) -> T \| None` | 单条记录或 `None` | 按全局 ID 查找 |
| `get_all` | `() -> List[T]` | 所有记录列表 | 返回顺序不保证 |
| `records` | `() -> Dict[ID, T]` | `{ID: 记录}` 字典 | AccountManager 按 display_order 排序 |
| `filter` | `(predicate: Callable[[T], bool]) -> List[T]` | 过滤后的列表 | Lambda 过滤 |
| `find_one` | `(predicate: Callable[[T], bool]) -> T \| None` | 第一个匹配或 `None` | — |
| `count` | `() -> int` | 记录总数 | — |

**示例：**

```python
# 按 ID 查找
account = api.account_manager.get(42)

# 按 GID 查找
category = api.category_manager.get_by_gid("some-gid-string")

# Lambda 过滤
results = api.payee_manager.filter(lambda p: "超市" in p.name)

# 找第一个匹配
tag = api.tag_manager.find_one(lambda t: t.name == "旅行")

# 总数
print(api.transaction_manager.count())
```

---

### 5.2 AccountManager

**文件：** `src/moneywiz_api/managers/account_manager.py`

支持的账户类型：`BankChequeAccount`、`BankSavingAccount`、`CashAccount`、`CreditCardAccount`、`LoanAccount`、`InvestmentAccount`、`ForexAccount`

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `records` | `() -> Dict[ID, Account]` | 按 `display_order` 排序 | 覆盖基类 |
| `get_accounts_for_user` | `(user_id: ID) -> List[Account]` | 账户列表 | 按 `(group_id, display_order)` 排序 |
| `get_by_name` | `(name: str, user_id: ID \| None = None) -> Account \| None` | 单个账户或 `None` | 精确名称匹配，找到第一个即返回 |
| `get_name` | `(account_id: ID) -> str` | 账户名称字符串 | 记录不存在时返回空字符串 `""` |

**示例：**

```python
# 获取用户 2 的所有账户
accounts = api.account_manager.get_accounts_for_user(user_id=2)

# 按名称查找
account = api.account_manager.get_by_name("招商银行储蓄卡")

# 获取账户名（用于显示）
name = api.account_manager.get_name(account_id=15)
```

---

### 5.3 CategoryManager

**文件：** `src/moneywiz_api/managers/category_manager.py`

支持的类型：`Category`（单一类，通过 `parent_id` 构成树形结构）

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_name_chain` | `(category_id: ID) -> List[str]` | 名称列表（根→叶） | 如 `["Transportation", "Car Fuel"]` |
| `get_name_chain_by_gid` | `(category_gid: GID) -> List[str]` | 名称列表 | 同上，按 GID 查找 |
| `get_categories_for_user` | `(user_id: ID) -> List[Category]` | 分类列表 | 按 `type`（Expenses/Income）排序 |
| `get_by_name` | `(name: str, user_id: ID \| None = None) -> List[Category]` | 分类列表 | 精确名称匹配，可能返回多个 |
| `search_by_name` | `(keyword: str, user_id: ID \| None = None) -> List[Category]` | 分类列表 | 关键词模糊搜索（忽略大小写） |
| `get_children` | `(category_id: ID) -> List[Category]` | 直接子分类列表 | 仅一级子节点 |
| `get_subtree_ids` | `(category_id: ID) -> Set[ID]` | ID 集合 | 含自身及所有后代（BFS），用于按分类查交易 |

**示例：**

```python
# 获取分类层级链
chain = api.category_manager.get_name_chain(category_id=88)
# 结果示例: ["Transportation", "Car Fuel"]
label = " > ".join(chain)  # "Transportation > Car Fuel"

# 模糊搜索分类
results = api.category_manager.search_by_name("餐", user_id=2)

# 获取分类及所有子分类 ID（用于查询交易）
subtree = api.category_manager.get_subtree_ids(category_id=50)
transactions = api.transaction_manager.get_by_category(list(subtree))
```

---

### 5.4 TransactionManager

**文件：** `src/moneywiz_api/managers/transaction_manager.py`

支持的交易类型（10 种）：`DepositTransaction`、`WithdrawTransaction`、`RefundTransaction`、`TransferBudgetTransaction`、`TransferDepositTransaction`、`TransferWithdrawTransaction`、`InvestmentExchangeTransaction`、`InvestmentBuyTransaction`、`InvestmentSellTransaction`、`ReconcileTransaction`

> `TransferBudgetTransaction` 在 `get_all`/`get_all_for_account`/`get_uncategorized`/`get_by_category` 中**自动过滤**，不会出现在结果中。

**额外属性（加载后可读）：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `category_assignment` | `Dict[ID, List[Tuple[ID, Decimal]]]` | 交易 ID → `[(分类ID, 金额)]` |
| `refund_maps` | `Dict[ID, ID]` | 退款交易 ID → 原始交易 ID |
| `tags_map` | `Dict[ID, ID]` | 交易 ID → 标签 ID |

**查询方法：**

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_all` | `(since: datetime \| None, until: datetime \| None) -> List[Transaction]` | 交易列表（按时间升序） | 排除 TransferBudgetTransaction |
| `get_all_for_account` | `(account_id: ID, since: datetime \| None, until: datetime \| None) -> List[Transaction]` | 交易列表（按时间升序） | 筛选含 `account` 字段且匹配的交易 |
| `get_uncategorized` | `(since: datetime \| None, until: datetime \| None) -> List[Transaction]` | 交易列表 | 无分类分配的交易 |
| `get_by_category` | `(category_ids: ID \| List[ID], since: datetime \| None, until: datetime \| None) -> List[Transaction]` | 交易列表 | 按分类 ID（支持列表）查询 |

**关联查询方法：**

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `category_for_transaction` | `(transaction_id: ID) -> List[Tuple[ID, Decimal]] \| None` | `[(分类ID, 金额)]` 或 `None` | 获取交易的分类分配 |
| `tags_for_transaction` | `(transaction_id: ID) -> List[ID] \| None` | 标签 ID 列表或 `None` | 获取交易的标签 |
| `original_transaction_for_refund_transaction` | `(transaction_id: ID) -> ID \| None` | 原始交易 ID 或 `None` | 获取退款对应的原交易 |

**示例：**

```python
from datetime import datetime

# 获取所有交易
all_txns = api.transaction_manager.get_all()

# 时间范围过滤
since = datetime(2024, 1, 1)
until = datetime(2024, 12, 31, 23, 59, 59)
txns_2024 = api.transaction_manager.get_all(since=since, until=until)

# 某账户的交易
txns = api.transaction_manager.get_all_for_account(account_id=15, since=since)

# 未分类交易
uncategorized = api.transaction_manager.get_uncategorized()

# 按分类查询（含子分类）
cat_ids = list(api.category_manager.get_subtree_ids(category_id=50))
txns = api.transaction_manager.get_by_category(cat_ids, since=since, until=until)

# 查询某交易的分类
cats = api.transaction_manager.category_for_transaction(transaction_id=1234)
# 结果示例: [(50, Decimal("88.00")), (51, Decimal("12.00"))]
```

---

### 5.5 PayeeManager

**文件：** `src/moneywiz_api/managers/payee_manager.py`

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_by_name` | `(name: str, user_id: ID \| None = None) -> Payee \| None` | 单个收款人或 `None` | 精确匹配，找到第一个即返回 |
| `search_by_name` | `(keyword: str, user_id: ID \| None = None) -> List[Payee]` | 收款人列表 | 关键词模糊搜索（忽略大小写） |
| `get_name` | `(payee_id: ID) -> str` | 收款人名称 | 不存在时返回空字符串 `""` |

---

### 5.6 TagManager

**文件：** `src/moneywiz_api/managers/tag_manager.py`

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_by_name` | `(name: str, user_id: ID \| None = None) -> Tag \| None` | 单个标签或 `None` | 精确匹配，找到第一个即返回 |
| `search_by_name` | `(keyword: str, user_id: ID \| None = None) -> List[Tag]` | 标签列表 | 关键词模糊搜索（忽略大小写） |
| `get_name` | `(tag_id: ID) -> str` | 标签名称 | 不存在时返回空字符串 `""` |

---

### 5.7 InvestmentHoldingManager

**文件：** `src/moneywiz_api/managers/investment_holding_manager.py`

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `get_holdings_for_account` | `(account_id: ID) -> List[InvestmentHolding]` | 持仓列表 | 获取某投资账户的所有持仓 |

> `update_last_price()` 和 `update_price_table()` 尚未实现，调用会抛出 `NotImplementedError`。

---

## 6. 数据模型参考

所有模型均为 Python dataclass，继承自 `Record` 基类。

### 6.1 Record 基类

**文件：** `src/moneywiz_api/model/record.py`

所有模型共有的字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `ID (int)` | 主键 (Z_PK)，在 repr 中显示 |
| `gid` | `str` | 全局唯一 ID (ZGID)，repr 中隐藏 |

序列化方法：

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `as_dict() -> Dict[str, Any]` | dataclass 字典，排除 `_` 前缀字段 | `Decimal` 和 `datetime` 保持原始类型 |
| `to_dict() -> Dict[str, Any]` | JSON 友好字典 | `Decimal → float`，`datetime → ISO 字符串` |
| `filtered() -> Dict[str, Any]` | 清理后的原始 SQLite 行数据 | 排除二进制字段和 Z9_ 前缀字段 |
| `ent() -> ENT_ID` | 实体类型 ID | 对应 SQLite 的 `Z_ENT` 列 |

---

### 6.2 Account 及子类

**文件：** `src/moneywiz_api/model/account.py`

**Account 基类字段（所有账户类型共有）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 账户名称 |
| `currency` | `str` | 货币代码（如 `"CNY"`） |
| `opening_balance` | `Decimal` | 期初余额 |
| `info` | `str` | 备注信息 |
| `user` | `ID` | 所属用户 ID |
| `display_order` | `int` | 显示排序（隐藏） |
| `group_id` | `Optional[int]` | 分组 ID（隐藏） |

**账户子类：**

| 类名 | ENT | 额外字段 | 说明 |
|------|-----|----------|------|
| `BankChequeAccount` | 10 | 无 | 银行支票账户 |
| `BankSavingAccount` | 11 | 无 | 银行储蓄账户 |
| `CashAccount` | 12 | 无 | 现金账户 |
| `CreditCardAccount` | 13 | `statement_day: int`（月结日） | 信用卡账户 |
| `LoanAccount` | 14 | `statement_day: int`（继承自 CreditCard） | 贷款账户 |
| `InvestmentAccount` | 15 | 无 | 投资账户 |
| `ForexAccount` | 16 | 无（继承自 InvestmentAccount） | 外汇账户 |

**类型判断示例：**

```python
from moneywiz_api.model.account import CreditCardAccount, InvestmentAccount

accounts = api.account_manager.get_all()
credit_cards = [a for a in accounts if isinstance(a, CreditCardAccount)]
investment_accounts = [a for a in accounts if isinstance(a, InvestmentAccount)]
```

---

### 6.3 Transaction 及子类

**文件：** `src/moneywiz_api/model/transaction/`

**Transaction 基类字段（所有交易类型共有）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `amount` | `Decimal` | 交易金额（负=支出/转出，正=收入/转入） |
| `description` | `str` | 交易描述 |
| `datetime` | `datetime` | 交易时间（含时区信息） |
| `notes` | `Optional[str]` | 备注 |
| `reconciled` | `bool` | 是否已对账 |

**Transaction 属性（注入后可读）：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `categories` | `List[CategoryAssignment]` | 所有分类分配列表 |
| `category_id` | `Optional[ID]` | 第一个分类 ID（多数交易只有一个分类） |

**Transaction 序列化：**

`to_dict()` 的结果额外包含 `categories` 数组：
```json
{
  "categories": [
    {"category_id": 50, "amount": 88.0},
    {"category_id": 51, "amount": 12.0}
  ]
}
```

---

**具体交易子类：**

#### DepositTransaction（存款/收入）ENT: 37

| 字段 | 类型 | 说明 |
|------|------|------|
| `account` | `ID` | 账户 ID |
| `amount` | `Decimal` | 正数=收入，负数=支出 |
| `payee` | `Optional[ID]` | 收款人 ID |
| `original_currency` | `str` | 原始货币 |
| `original_amount` | `Decimal` | 原始金额 |
| `original_exchange_rate` | `Optional[Decimal]` | 汇率 |

#### WithdrawTransaction（取款/支出）ENT: 47

字段同 `DepositTransaction`，`original_amount` 已修正为正数。

#### RefundTransaction（退款）ENT: 43

字段同 `DepositTransaction`，`amount` 和 `original_amount` 均为正数。

#### TransferDepositTransaction（转入）ENT: 45

| 字段 | 类型 | 说明 |
|------|------|------|
| `account` | `ID` | 接收账户 ID |
| `amount` | `Decimal` | 接收金额（正数） |
| `sender_account` | `ID` | 发送账户 ID |
| `sender_transaction` | `ID` | 对应的转出交易 ID |
| `original_amount` | `Decimal` | 原始金额（正数） |
| `original_currency` | `str` | 原始货币 |
| `sender_amount` | `Decimal` | 发送金额（负数） |
| `sender_currency` | `str` | 发送货币 |
| `original_fee` | `Optional[Decimal]` | 手续费 |
| `original_fee_currency` | `Optional[str]` | 手续费货币 |
| `original_exchange_rate` | `Decimal` | 汇率 |

#### TransferWithdrawTransaction（转出）ENT: 46

| 字段 | 类型 | 说明 |
|------|------|------|
| `account` | `ID` | 发送账户 ID |
| `amount` | `Decimal` | 发送金额（负数） |
| `recipient_account` | `ID` | 接收账户 ID |
| `recipient_transaction` | `ID` | 对应的转入交易 ID |
| `original_amount` | `Decimal` | 原始金额（负数） |
| `original_currency` | `str` | 原始货币 |
| `recipient_amount` | `Decimal` | 接收金额（正数） |
| `recipient_currency` | `str` | 接收货币 |
| `original_fee` | `Optional[Decimal]` | 手续费 |
| `original_fee_currency` | `Optional[str]` | 手续费货币 |
| `original_exchange_rate` | `Decimal` | 汇率 |

#### InvestmentBuyTransaction（买入）ENT: 40

| 字段 | 类型 | 说明 |
|------|------|------|
| `account` | `ID` | 投资账户 ID |
| `amount` | `Decimal` | 支出金额（≤0） |
| `fee` | `Decimal` | 手续费（≥0） |
| `investment_holding` | `ID` | 持仓 ID |
| `number_of_shares` | `Decimal` | 购买股数（正数） |
| `price_per_share` | `Decimal` | 单价（≥0） |

#### InvestmentSellTransaction（卖出）ENT: 41

字段同 `InvestmentBuyTransaction`，`amount` 可正可负（亏损时为负）。

#### InvestmentExchangeTransaction（品种兑换）ENT: 38

| 字段 | 类型 | 说明 |
|------|------|------|
| `account` | `ID` | 投资账户 ID |
| `from_investment_holding` | `ID` | 源持仓 ID |
| `from_symbol` | `str` | 源股票代码 |
| `to_investment_holding` | `ID` | 目标持仓 ID |
| `to_symbol` | `str` | 目标股票代码 |
| `from_number_of_shares` | `Decimal` | 源持股数（负数） |
| `to_number_of_shares` | `Decimal` | 目标持股数（正数） |
| `original_fee` | `Decimal` | 手续费 |
| `original_fee_currency` | `str` | 手续费货币 |

#### ReconcileTransaction（对账）ENT: 42

| 字段 | 类型 | 说明 |
|------|------|------|
| `account` | `ID` | 账户 ID |
| `reconcile_amount` | `Optional[Decimal]` | 对账后余额（普通账户） |
| `reconcile_number_of_shares` | `Optional[Decimal]` | 对账后持股数（投资账户） |

> `reconcile_amount` 和 `reconcile_number_of_shares` 至少一个不为 `None`。

#### TransferBudgetTransaction ENT: 44

内部预算转账，**在所有常用查询方法中自动过滤**，不建议直接使用。

---

### 6.4 Category

**文件：** `src/moneywiz_api/model/category.py` | ENT: 19

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 分类名称 |
| `parent_id` | `Optional[ID]` | 父分类 ID，顶级分类为 `None` |
| `type` | `CategoryType` | `"Expenses"` 或 `"Income"` |
| `user` | `ID` | 所属用户 ID |

---

### 6.5 Payee

**文件：** `src/moneywiz_api/model/payee.py` | ENT: 28

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 收款人名称 |
| `user` | `ID` | 所属用户 ID |

---

### 6.6 Tag

**文件：** `src/moneywiz_api/model/tag.py` | ENT: 35

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 标签名称 |
| `user` | `ID` | 所属用户 ID |

---

### 6.7 InvestmentHolding

**文件：** `src/moneywiz_api/model/investment_holding.py` | ENT: 24

| 字段 | 类型 | 说明 |
|------|------|------|
| `account` | `ID` | 所属投资账户 ID |
| `symbol` | `str` | 股票/基金代码 |
| `description` | `str` | 持仓描述/名称 |
| `number_of_shares` | `Decimal` | 当前持股数 |
| `opening_number_of_shares` | `Optional[Decimal]` | 期初持股数 |
| `holding_type` | `Optional[str]` | 持仓类型 |
| `price_per_share_available_online` | `bool` | 是否可在线获取价格 |

---

## 7. CLI 参考

**命令：** `moneywiz-cli`

```bash
moneywiz-cli [OPTIONS] [DB_FILE_PATH]
```

**参数：**

| 参数/选项 | 默认值 | 说明 |
|-----------|--------|------|
| `DB_FILE_PATH` | macOS 标准路径 | SQLite 数据库路径 |
| `-d, --demo-dump` | `False` | 启动时输出用户/分类/账户样本数据 |
| `--log-level` | `INFO` | 日志级别：`DEBUG\|INFO\|WARNING\|ERROR\|CRITICAL` |

**macOS 默认路径：**
```
~/Library/Containers/com.moneywiz.personalfinance/Data/Documents/.AppData/ipadMoneyWiz.sqlite
```

**启动后 shell 内置变量：**

| 变量名 | 类型 | 说明 |
|--------|------|------|
| `moneywiz_api` | `MoneywizApi` | 门面类实例 |
| `accessor` | `DatabaseAccessor` | 数据库访问器 |
| `account_manager` | `AccountManager` | — |
| `payee_manager` | `PayeeManager` | — |
| `category_manager` | `CategoryManager` | — |
| `transaction_manager` | `TransactionManager` | — |
| `investment_holding_manager` | `InvestmentHoldingManager` | — |
| `tag_manager` | `TagManager` | — |
| `helper` | `ShellHelper` | 便捷辅助工具，DataFrame 输出 |

**ShellHelper 方法：**

| 方法 | 签名 | 返回值 | 说明 |
|------|------|--------|------|
| `view_id` | `(record_id: ID)` | 无（打印输出） | 按主键查看原始记录（JSON） |
| `view_gid` | `(record_gid: GID)` | 无（打印输出） | 按 GID 查看原始记录（JSON） |
| `pd_table` | `(manager: RecordManager) -> pd.DataFrame` | DataFrame | 将任意 Manager 转为 DataFrame |
| `users_table` | `() -> pd.DataFrame` | DataFrame | 用户表，列：`id`, `login_name` |
| `categories_table` | `(user_id: ID) -> pd.DataFrame` | DataFrame | 指定用户的分类表 |
| `accounts_table` | `(user_id: ID) -> pd.DataFrame` | DataFrame | 指定用户的账户表 |
| `investment_holdings_table` | `(account_id: ID) -> pd.DataFrame` | DataFrame | 指定账户的持仓表 |
| `transactions_table` | `(account_id: ID) -> pd.DataFrame` | DataFrame | 指定账户的交易表（含 `category` 列，格式为 `"A > B"`） |
| `transactions_by_category_table` | `(category_id: ID, include_subcategories: bool = True, since: datetime \| None = None, until: datetime \| None = None) -> pd.DataFrame` | DataFrame | 按分类查询交易表，支持子分类和时间过滤 |
| `write_stats_data_files` | `(path_prefix: Path = Path("data/stats"))` | 无 | 将所有数据导出为 `.data` 文件 |

---

## 8. 常用查询模式

### 8.1 获取用户账户列表

```python
with MoneywizApi(db_path) as api:
    # 获取用户表（先确认 user_id）
    users = api.accessor.get_users()
    # users 示例: {1: "system", 2: "alice@example.com"}

    # 获取用户 2 的所有账户
    accounts = api.account_manager.get_accounts_for_user(user_id=2)
    for acct in accounts:
        print(f"[{acct.id}] {acct.name} ({acct.currency}): {acct.opening_balance}")
```

### 8.2 按分类（含子分类）查询交易

```python
with MoneywizApi(db_path) as api:
    # 找到"餐饮"分类
    cats = api.category_manager.search_by_name("餐饮", user_id=2)
    cat = cats[0]

    # 获取该分类及所有子分类的交易
    subtree_ids = api.category_manager.get_subtree_ids(cat.id)
    txns = api.transaction_manager.get_by_category(list(subtree_ids))
    print(f"共 {len(txns)} 笔餐饮相关交易")
```

### 8.3 获取未分类交易

```python
from datetime import datetime

with MoneywizApi(db_path) as api:
    since = datetime(2024, 1, 1)
    uncategorized = api.transaction_manager.get_uncategorized(since=since)
    for txn in uncategorized:
        print(f"{txn.datetime.date()} | {txn.description} | {txn.amount}")
```

### 8.4 拼接分类层级链

```python
with MoneywizApi(db_path) as api:
    txns = api.transaction_manager.get_all()
    for txn in txns:
        if txn.category_id:
            chain = api.category_manager.get_name_chain(txn.category_id)
            label = " > ".join(chain)  # 例如 "Transportation > Car Fuel"
```

### 8.5 计算账户余额

```python
from decimal import Decimal
from datetime import datetime

with MoneywizApi(db_path) as api:
    account = api.account_manager.get_by_name("招商银行储蓄卡")
    as_of = datetime(2024, 12, 31, 23, 59, 59)

    txns = api.transaction_manager.get_all_for_account(account.id, until=as_of)
    balance = account.opening_balance
    for txn in txns:
        balance += txn.amount
    print(f"余额: {balance} {account.currency}")
```

### 8.6 投资持仓追踪

```python
from collections import defaultdict
from moneywiz_api.model.transaction import InvestmentBuyTransaction, InvestmentSellTransaction

with MoneywizApi(db_path) as api:
    inv_account = api.account_manager.get_by_name("证券账户")
    txns = api.transaction_manager.get_all_for_account(inv_account.id)

    shares: dict = defaultdict(lambda: Decimal("0"))
    for txn in txns:
        if isinstance(txn, InvestmentBuyTransaction):
            shares[txn.investment_holding] += txn.number_of_shares
        elif isinstance(txn, InvestmentSellTransaction):
            shares[txn.investment_holding] -= txn.number_of_shares

    for holding_id, qty in shares.items():
        holding = api.investment_holding_manager.get(holding_id)
        print(f"{holding.symbol}: {qty} 股")
```

### 8.7 序列化为 JSON

```python
import json

with MoneywizApi(db_path) as api:
    txns = api.transaction_manager.get_all()
    data = [txn.to_dict() for txn in txns]  # Decimal→float, datetime→ISO
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
```

---

## 9. AI Agent 调用指引

本节为 AI Agent 提供按场景的快速接口索引。

### 初始化

```python
from pathlib import Path
from moneywiz_api import MoneywizApi

api = MoneywizApi(Path("/path/to/ipadMoneyWiz.sqlite"))
# 或使用上下文管理器（推荐）
```

### 场景索引

| 目标 | 调用路径 |
|------|---------|
| 获取所有账户 | `api.account_manager.get_all()` |
| 按用户获取账户 | `api.account_manager.get_accounts_for_user(user_id)` |
| 按账户名查找 | `api.account_manager.get_by_name(name)` |
| 获取所有交易 | `api.transaction_manager.get_all(since?, until?)` |
| 获取某账户交易 | `api.transaction_manager.get_all_for_account(account_id, since?, until?)` |
| 获取未分类交易 | `api.transaction_manager.get_uncategorized(since?, until?)` |
| 按分类查询交易 | `api.transaction_manager.get_by_category(category_ids, since?, until?)` |
| 获取分类层级链 | `api.category_manager.get_name_chain(category_id)` → `List[str]` |
| 搜索分类 | `api.category_manager.search_by_name(keyword, user_id?)` |
| 获取分类子树 ID | `api.category_manager.get_subtree_ids(category_id)` → `Set[ID]` |
| 搜索收款人 | `api.payee_manager.search_by_name(keyword)` |
| 搜索标签 | `api.tag_manager.search_by_name(keyword)` |
| 获取投资持仓 | `api.investment_holding_manager.get_holdings_for_account(account_id)` |
| 查询交易的分类 | `api.transaction_manager.category_for_transaction(transaction_id)` |
| 查询交易的标签 | `api.transaction_manager.tags_for_transaction(transaction_id)` |
| 序列化为 JSON | `record.to_dict()` |

### 关键字段速查

| 获取内容 | 字段路径 |
|----------|---------|
| 交易金额（含符号） | `transaction.amount` |
| 交易时间 | `transaction.datetime` |
| 交易所属账户 | `transaction.account` (ID) |
| 交易首个分类 | `transaction.category_id` (ID or None) |
| 交易所有分类 | `transaction.categories` (List[CategoryAssignment]) |
| 分类名称层级 | `category_manager.get_name_chain(category_id)` |
| 账户货币 | `account.currency` |
| 账户期初余额 | `account.opening_balance` |

### 注意事项

1. **amount 符号**：负数=支出/转出，正数=收入/转入，`ReconcileTransaction` 没有此语义
2. **TransferBudgetTransaction**：内部预算记录，`get_all` 等方法已自动排除
3. **多用户数据库**：MoneyWiz 支持多用户（家庭共享），建议使用 `user_id` 参数过滤
4. **分类多分配**：一笔交易可分配到多个分类（`transaction.categories` 为列表），`category_id` 仅返回第一个
5. **user_id 获取**：通过 `api.accessor.get_users()` 获取 `{ID: login_name}` 字典
