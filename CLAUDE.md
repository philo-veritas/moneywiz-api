# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

moneywiz-api 是一个只读 Python 库，用于访问 MoneyWiz 个人理财应用的 SQLite 数据库。提供账户、交易、分类、收款人、标签、投资持仓的查询能力，以及交互式 CLI Shell。

## 常用命令

```bash
uv sync                              # 安装依赖
uv run ruff check src/               # lint
uv run ruff format src/ tests/       # 格式化
uv run pytest tests/unit -v          # 单元测试
uv run pytest tests/unit/test_utils.py::test_get_datetime_roundtrip  # 单个测试
uv run pytest tests                  # 全部测试（集成测试需要本机有 MoneyWiz DB）
uv run mypy src                      # 类型检查
uv run moneywiz-cli                  # 交互式 shell（默认读取 macOS MoneyWiz DB）
uv run moneywiz-cli /path/to/db.sqlite  # 指定 DB 路径
```

## 架构

数据流：**SQLite → DatabaseAccessor → RecordManager[T] → Model → MoneywizApi → CLI/ShellHelper**

- **`DatabaseAccessor`** (`database_accessor.py`): 直接操作 SQLite，通过 `Z_PRIMARYKEY` 表将 `Z_ENT` 数字映射到类型名称（如 37→DepositTransaction），批量从 `ZSYNCOBJECT` 表查询记录。额外加载关联数据：分类分配、退款映射、标签映射。
- **`RecordManager[T]`** (`managers/record_manager.py`): 泛型基类，子类只需定义 `ents` 属性（类型名→构造函数映射），即可自动完成加载、索引（by ID/GID）和查询。6 个 Manager 都继承此基类。
- **Model 层** (`model/`): 全部为 dataclass，继承 `Record` 基类。构造函数从 SQLite row dict 中提取字段并做类型转换（通过 `RawDataHandler` 处理 Decimal/datetime）和断言校验。
- **`MoneywizApi`** (`moneywiz_api.py`): 门面类，初始化时自动加载所有 Manager。支持上下文管理器。
- **CLI** (`cli/`): Click 命令启动交互式 Python shell，`ShellHelper` 将 Manager 数据转为 pandas DataFrame。

### 关键类型 (`types.py`)

- `ID = int` — 主键 (Z_PK)
- `GID = str` — 全局唯一 ID
- `ENT_ID = int` — 实体类型 ID (Z_ENT)

### Transaction 子包结构 (`model/transaction/`)

按职责拆分为 `base.py`（Transaction ABC）、`deposit.py`（Deposit/Withdraw/Refund）、`transfer.py`（TransferBudget/Deposit/Withdraw）、`investment.py`（InvestmentExchange/Buy/Sell）、`reconcile.py`。`__init__.py` 重导出所有类，外部 import 路径不变。

### MoneyWiz SQLite 约定

- 所有实体存储在 `ZSYNCOBJECT` 单表中，通过 `Z_ENT` 区分类型
- 时间戳是相对于 2001-01-01 00:00:00 的 float 秒数（Core Data epoch）
- 金额为 float，代码中转为 `Decimal` 保证精度
- 列名以 `Z` 前缀命名（如 `ZAMOUNT1`、`ZACCOUNT2`、`ZDESC2`）
- 多对多关联表名动态生成，格式如 `Z_{ent}TAGS`

## 测试

- **单元测试** (`tests/unit/`): 不依赖外部数据，可随时运行
- **集成测试** (`tests/integration/`): 依赖本机 MoneyWiz SQLite 数据库（macOS 默认路径），DB 不存在时自动 skip。集成测试使用模块级变量（非 fixture），因为 `@pytest.mark.parametrize` 在收集阶段需要数据
- CI 只运行单元测试（`pytest tests/unit`）
