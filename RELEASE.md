# RELEASE

`moneywiz-db-api` 是独立 fork 包，版本线从 `0.1.1` 往后走。
上游 `moneywiz-api` 的 `v1.x` tag 仅是历史记录，不参与这个包的版本决策。

## 标准流程

标准发版路径是：

`scripts/release.py` -> GitHub Release -> GitHub Actions -> PyPI

标准命令：

```bash
uv run python scripts/release.py patch
uv run python scripts/release.py minor
uv run python scripts/release.py major
```

不要把“push tag”当成发版完成。当前自动发布 workflow 只会在 GitHub Release 被 `Publish` 后触发。

## 发版前提

- 从 `main` 发版。
- 工作区保持干净，避免把未提交改动混进 release。
- 你有 GitHub 仓库发布权限。
- PyPI 上的 `moneywiz-db-api` 已配置 Trusted Publisher，并绑定当前仓库的 `.github/workflows/python-publish.yml` 和 `pypi` environment。

## 脚本会做什么

脚本固定接受 `patch|minor|major` 三种参数，并自动完成以下步骤：

1. 检查当前分支必须是 `main`，且工作区干净
2. 检查 `git`、`gh`、`uv` 可用，且 `gh auth status` 通过
3. `git fetch origin main --tags`，确保本地 `main` 没有落后于 `origin/main`
4. 根据 `patch|minor|major` 计算新版本，更新 `pyproject.toml` 并执行 `uv lock`
5. 运行发布前检查：

   ```bash
   uv run ruff check src/
   uv run pytest tests/unit -v
   uv run mypy src
   ```

6. 自动创建 release commit：`chore(release): vX.Y.Z`
7. 自动创建 annotated tag：`vX.Y.Z`
8. 自动 push `main` 和 tag
9. 用 `gh release create --generate-notes` 创建并发布 GitHub Release
10. 等待 `Upload Python Package` workflow 成功，最后输出 Release 和 PyPI 链接

如果脚本在远端操作之后失败，它不会自动回滚已推送的 commit、tag 或 Release，只会直接报错并保留现场。

## 手工兜底

如果自动发布失败，常见原因是 Trusted Publisher / OIDC 配置有误，或者发布脚本已经创建了 GitHub Release 但 workflow 失败。这时可以走本地 Twine 兜底路径。

前提：

- `pyproject.toml` 和 `uv.lock` 已同步到目标版本
- 发布前检查已经通过
- 本机已配置 PyPI 凭据，例如 `~/.pypirc` 或 `TWINE_*` 环境变量

步骤：

1. 清理本地旧产物，避免把历史文件一起传上去。

   ```bash
   rm -rf dist/
   ```

2. 构建发布产物。

   ```bash
   make package
   ```

3. 可选：先发到 TestPyPI 预演。

   ```bash
   make test-publish
   ```

4. 发正式 PyPI。

   ```bash
   make publish
   ```

5. 回到 PyPI 页面确认版本更新。

## 常见失败点

- 只 push 了 tag，但没有在 GitHub 上 `Publish release`
- `pyproject.toml` 和 `uv.lock` 的版本不一致
- Trusted Publisher 绑定了错误的仓库、workflow 或 environment
- 本地手工发布前没有清理 `dist/`，导致上传了旧文件
