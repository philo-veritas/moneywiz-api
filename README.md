# moneywiz-db-api

> 这是 [moneywiz-api](https://github.com/ileodo/moneywiz-api) 的 fork 版本。
> 原项目已数月未更新，此版本用于持续维护和功能增强。感谢原作者 [iLeoDo](https://github.com/ileodo) 的贡献。

![Static Badge](https://img.shields.io/badge/Python-3-blue?style=flat&logo=Python)
![PyPI](https://img.shields.io/pypi/v/moneywiz-db-api)

A Python API to access MoneyWiz Sqlite database.

## Get Started

```bash
pip install moneywiz-db-api
# 或使用 uv
uv add moneywiz-db-api
```

```python
from moneywiz_api import MoneywizApi

# 使用默认 macOS MoneyWiz 数据库路径
with MoneywizApi() as api:
    # 获取所有交易
    transactions = api.transaction_manager.get_all()

    # 获取所有分类
    categories = api.category_manager.get_all()

    # 查询无分类交易
    uncategorized = api.transaction_manager.get_uncategorized_transactions()

# 或指定数据库路径
with MoneywizApi("<path_to_your_sqlite_file>") as api:
    record = api.accessor.get_record(record_id)
    print(record)
```

## Interactive CLI

本包提供交互式命令行工具 `moneywiz-cli`：

```bash
# 使用默认数据库路径
moneywiz-cli

# 指定数据库路径
moneywiz-cli /path/to/moneywiz.sqlite
```

## Contribution

This project is in very early stage, all contributions are welcomed!
