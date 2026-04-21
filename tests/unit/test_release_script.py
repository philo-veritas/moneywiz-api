import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load_release_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "release.py"
    )
    spec = importlib.util.spec_from_file_location("release_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release = _load_release_module()


class FakeRunner:
    def __init__(self, module, responses):
        self.module = module
        self.responses = {tuple(command): list(items) for command, items in responses.items()}
        self.commands = []

    def __call__(self, args, *, cwd, capture_output, check):
        key = tuple(args)
        self.commands.append(key)
        queue = self.responses.get(key)
        if not queue:
            raise AssertionError(f"Unexpected command: {key!r}")

        response = queue.pop(0)
        if callable(response):
            response = response(args, cwd=cwd, capture_output=capture_output, check=check)

        if isinstance(response, subprocess.CompletedProcess):
            completed = response
        else:
            returncode, stdout, stderr = response
            completed = subprocess.CompletedProcess(
                list(args), returncode, stdout=stdout, stderr=stderr
            )

        if check and completed.returncode != 0:
            raise self.module.ReleaseError(
                f"命令执行失败: {' '.join(args)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        return completed


def _write_release_files(tmp_path, version="0.1.1"):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "\n".join(
            [
                "[build-system]",
                'requires = ["setuptools>=61.0"]',
                'build-backend = "setuptools.build_meta"',
                "",
                "[project]",
                'name = "moneywiz-db-api"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text('version = 1\nname = "moneywiz-db-api"\n', encoding="utf-8")
    return pyproject, uv_lock


def _write_version_side_effect(
    pyproject, version, *, returncode=0, stdout="", stderr=""
):
    def callback(*_, **__):
        release.write_project_version(pyproject, release.Version.parse(version))
        return (returncode, stdout, stderr)

    return callback


def _write_lock_side_effect(uv_lock, content, *, returncode=0, stdout="", stderr=""):
    def callback(*_, **__):
        uv_lock.write_text(content, encoding="utf-8")
        return (returncode, stdout, stderr)

    return callback


def test_version_bump_variants():
    current = release.Version.parse("0.1.1")

    assert str(current.bump("patch")) == "0.1.2"
    assert str(current.bump("minor")) == "0.2.0"
    assert str(current.bump("major")) == "1.0.0"


def test_read_and_write_project_version(tmp_path):
    pyproject, _ = _write_release_files(tmp_path, version="0.1.1")

    assert str(release.read_project_version(pyproject)) == "0.1.1"

    release.write_project_version(pyproject, release.Version.parse("0.2.0"))

    assert str(release.read_project_version(pyproject)) == "0.2.0"


def test_release_patch_runs_expected_commands_in_order(tmp_path):
    pyproject, uv_lock = _write_release_files(tmp_path, version="0.1.1")
    stdout = io.StringIO()
    responses = {
        ("git", "branch", "--show-current"): [(0, "main\n", "")],
        ("git", "status", "--porcelain"): [(0, "", "")],
        ("gh", "auth", "status"): [(0, "", "")],
        ("git", "fetch", "origin", "main", "--tags"): [(0, "", "")],
        ("git", "rev-list", "--left-right", "--count", "HEAD...origin/main"): [
            (0, "0\t0\n", "")
        ],
        ("git", "rev-parse", "--verify", "--quiet", "refs/tags/v0.1.2"): [
            (1, "", "")
        ],
        ("uv", "lock"): [(0, "", "")],
        ("uv", "run", "ruff", "check", "src/"): [(0, "", "")],
        ("uv", "run", "pytest", "tests/unit", "-v"): [(0, "", "")],
        ("uv", "run", "mypy", "src"): [(0, "", "")],
        ("git", "add", "pyproject.toml", "uv.lock"): [(0, "", "")],
        ("git", "commit", "-m", "chore(release): v0.1.2"): [(0, "", "")],
        ("git", "rev-parse", "HEAD"): [(0, "abc123\n", "")],
        ("git", "tag", "-a", "v0.1.2", "-m", "v0.1.2"): [(0, "", "")],
        ("git", "push", "origin", "main"): [(0, "", "")],
        ("git", "push", "origin", "v0.1.2"): [(0, "", "")],
        (
            "gh",
            "release",
            "create",
            "v0.1.2",
            "--title",
            "v0.1.2",
            "--generate-notes",
            "--verify-tag",
        ): [(0, "https://github.com/philo-veritas/moneywiz-api/releases/tag/v0.1.2\n", "")],
        (
            "gh",
            "run",
            "list",
            "--workflow",
            release.WORKFLOW_NAME,
            "--event",
            "release",
            "--json",
            "databaseId,headSha,status,conclusion,url",
            "-L",
            "20",
        ): [
            (0, "[]", ""),
            (
                0,
                json.dumps(
                    [
                        {
                            "databaseId": 42,
                            "headSha": "abc123",
                            "status": "in_progress",
                            "conclusion": None,
                            "url": "https://github.com/philo-veritas/moneywiz-api/actions/runs/42",
                        }
                    ]
                ),
                "",
            ),
            (
                0,
                json.dumps(
                    [
                        {
                            "databaseId": 42,
                            "headSha": "abc123",
                            "status": "completed",
                            "conclusion": "success",
                            "url": "https://github.com/philo-veritas/moneywiz-api/actions/runs/42",
                        }
                    ]
                ),
                "",
            ),
        ],
        ("gh", "run", "watch", "42", "--compact", "--exit-status"): [(0, "", "")],
    }
    runner = FakeRunner(release, responses)
    sleeps = []
    manager = release.ReleaseManager(
        root=tmp_path,
        pyproject_path=pyproject,
        uv_lock_path=uv_lock,
        runner=runner,
        sleep_fn=lambda seconds: sleeps.append(seconds),
        which=lambda tool: f"/usr/bin/{tool}",
        stdout=stdout,
    )

    manager.release("patch")

    assert str(release.read_project_version(pyproject)) == "0.1.2"
    assert sleeps == [release.RUN_DISCOVERY_INTERVAL_SECONDS]
    assert runner.commands == [
        ("git", "branch", "--show-current"),
        ("git", "status", "--porcelain"),
        ("gh", "auth", "status"),
        ("git", "fetch", "origin", "main", "--tags"),
        ("git", "rev-list", "--left-right", "--count", "HEAD...origin/main"),
        ("git", "rev-parse", "--verify", "--quiet", "refs/tags/v0.1.2"),
        ("uv", "lock"),
        ("uv", "run", "ruff", "check", "src/"),
        ("uv", "run", "pytest", "tests/unit", "-v"),
        ("uv", "run", "mypy", "src"),
        ("git", "add", "pyproject.toml", "uv.lock"),
        ("git", "commit", "-m", "chore(release): v0.1.2"),
        ("git", "rev-parse", "HEAD"),
        ("git", "tag", "-a", "v0.1.2", "-m", "v0.1.2"),
        ("git", "push", "origin", "main"),
        ("git", "push", "origin", "v0.1.2"),
        (
            "gh",
            "release",
            "create",
            "v0.1.2",
            "--title",
            "v0.1.2",
            "--generate-notes",
            "--verify-tag",
        ),
        (
            "gh",
            "run",
            "list",
            "--workflow",
            release.WORKFLOW_NAME,
            "--event",
            "release",
            "--json",
            "databaseId,headSha,status,conclusion,url",
            "-L",
            "20",
        ),
        (
            "gh",
            "run",
            "list",
            "--workflow",
            release.WORKFLOW_NAME,
            "--event",
            "release",
            "--json",
            "databaseId,headSha,status,conclusion,url",
            "-L",
            "20",
        ),
        ("gh", "run", "watch", "42", "--compact", "--exit-status"),
        (
            "gh",
            "run",
            "list",
            "--workflow",
            release.WORKFLOW_NAME,
            "--event",
            "release",
            "--json",
            "databaseId,headSha,status,conclusion,url",
            "-L",
            "20",
        ),
    ]
    assert "Release completed successfully" in stdout.getvalue()
    assert release.PYPI_URL in stdout.getvalue()


def test_release_fails_when_worktree_is_dirty(tmp_path):
    pyproject, uv_lock = _write_release_files(tmp_path, version="0.1.1")
    runner = FakeRunner(
        release,
        {
            ("git", "branch", "--show-current"): [(0, "main\n", "")],
            ("git", "status", "--porcelain"): [(0, " M pyproject.toml\n", "")],
        },
    )
    manager = release.ReleaseManager(
        root=tmp_path,
        pyproject_path=pyproject,
        uv_lock_path=uv_lock,
        runner=runner,
        sleep_fn=lambda _: None,
        which=lambda tool: f"/usr/bin/{tool}",
    )

    with pytest.raises(release.ReleaseError, match="工作区不干净"):
        manager.release("patch")

    assert str(release.read_project_version(pyproject)) == "0.1.1"
    assert runner.commands == [
        ("git", "branch", "--show-current"),
        ("git", "status", "--porcelain"),
    ]


def test_release_fails_when_origin_main_is_ahead(tmp_path):
    pyproject, uv_lock = _write_release_files(tmp_path, version="0.1.1")
    runner = FakeRunner(
        release,
        {
            ("git", "branch", "--show-current"): [(0, "main\n", "")],
            ("git", "status", "--porcelain"): [(0, "", "")],
            ("gh", "auth", "status"): [(0, "", "")],
            ("git", "fetch", "origin", "main", "--tags"): [(0, "", "")],
            ("git", "rev-list", "--left-right", "--count", "HEAD...origin/main"): [
                (0, "0\t2\n", "")
            ],
        },
    )
    manager = release.ReleaseManager(
        root=tmp_path,
        pyproject_path=pyproject,
        uv_lock_path=uv_lock,
        runner=runner,
        sleep_fn=lambda _: None,
        which=lambda tool: f"/usr/bin/{tool}",
    )

    with pytest.raises(release.ReleaseError, match="origin/main 包含当前本地 main 没有的提交"):
        manager.release("patch")

    assert str(release.read_project_version(pyproject)) == "0.1.1"


def test_release_restores_version_files_when_uv_lock_fails(tmp_path):
    pyproject, uv_lock = _write_release_files(tmp_path, version="0.1.1")
    original_lock = uv_lock.read_text(encoding="utf-8")
    runner = FakeRunner(
        release,
        {
            ("git", "branch", "--show-current"): [(0, "main\n", "")],
            ("git", "status", "--porcelain"): [(0, "", "")],
            ("gh", "auth", "status"): [(0, "", "")],
            ("git", "fetch", "origin", "main", "--tags"): [(0, "", "")],
            ("git", "rev-list", "--left-right", "--count", "HEAD...origin/main"): [
                (0, "0\t0\n", "")
            ],
            ("git", "rev-parse", "--verify", "--quiet", "refs/tags/v0.1.2"): [
                (1, "", "")
            ],
            ("uv", "lock"): [
                _write_lock_side_effect(
                    uv_lock,
                    'version = 1\nname = "moneywiz-db-api"\npackage-version = "0.1.2"\n',
                    returncode=1,
                    stderr="uv lock failed",
                )
            ],
        },
    )
    manager = release.ReleaseManager(
        root=tmp_path,
        pyproject_path=pyproject,
        uv_lock_path=uv_lock,
        runner=runner,
        sleep_fn=lambda _: None,
        which=lambda tool: f"/usr/bin/{tool}",
    )

    with pytest.raises(release.ReleaseError, match="uv lock failed"):
        manager.release("patch")

    assert str(release.read_project_version(pyproject)) == "0.1.1"
    assert uv_lock.read_text(encoding="utf-8") == original_lock
    assert ("git", "add", "pyproject.toml", "uv.lock") not in runner.commands


def test_release_restores_version_files_when_checks_fail(tmp_path):
    pyproject, uv_lock = _write_release_files(tmp_path, version="0.1.1")
    original_lock = uv_lock.read_text(encoding="utf-8")
    runner = FakeRunner(
        release,
        {
            ("git", "branch", "--show-current"): [(0, "main\n", "")],
            ("git", "status", "--porcelain"): [(0, "", "")],
            ("gh", "auth", "status"): [(0, "", "")],
            ("git", "fetch", "origin", "main", "--tags"): [(0, "", "")],
            ("git", "rev-list", "--left-right", "--count", "HEAD...origin/main"): [
                (0, "0\t0\n", "")
            ],
            ("git", "rev-parse", "--verify", "--quiet", "refs/tags/v0.1.2"): [
                (1, "", "")
            ],
            ("uv", "lock"): [
                _write_lock_side_effect(
                    uv_lock,
                    'version = 1\nname = "moneywiz-db-api"\npackage-version = "0.1.2"\n',
                )
            ],
            ("uv", "run", "ruff", "check", "src/"): [
                _write_version_side_effect(
                    pyproject, "0.1.2", returncode=1, stderr="ruff failed"
                )
            ],
        },
    )
    manager = release.ReleaseManager(
        root=tmp_path,
        pyproject_path=pyproject,
        uv_lock_path=uv_lock,
        runner=runner,
        sleep_fn=lambda _: None,
        which=lambda tool: f"/usr/bin/{tool}",
    )

    with pytest.raises(release.ReleaseError, match="ruff failed"):
        manager.release("patch")

    assert str(release.read_project_version(pyproject)) == "0.1.1"
    assert uv_lock.read_text(encoding="utf-8") == original_lock
    assert ("git", "add", "pyproject.toml", "uv.lock") not in runner.commands


def test_wait_for_publish_run_raises_on_failed_workflow(tmp_path):
    pyproject, uv_lock = _write_release_files(tmp_path, version="0.1.1")
    responses = {
        (
            "gh",
            "run",
            "list",
            "--workflow",
            release.WORKFLOW_NAME,
            "--event",
            "release",
            "--json",
            "databaseId,headSha,status,conclusion,url",
            "-L",
            "20",
        ): [
            (
                0,
                json.dumps(
                    [
                        {
                            "databaseId": 77,
                            "headSha": "abc123",
                            "status": "completed",
                            "conclusion": "failure",
                            "url": "https://github.com/philo-veritas/moneywiz-api/actions/runs/77",
                        }
                    ]
                ),
                "",
            )
        ]
    }
    runner = FakeRunner(release, responses)
    manager = release.ReleaseManager(
        root=tmp_path,
        pyproject_path=pyproject,
        uv_lock_path=uv_lock,
        runner=runner,
        sleep_fn=lambda _: None,
        which=lambda tool: f"/usr/bin/{tool}",
    )

    with pytest.raises(release.ReleaseError, match="PyPI 发布 workflow 失败"):
        manager.wait_for_publish_run("abc123")

    assert ("gh", "run", "watch", "77", "--compact", "--exit-status") not in runner.commands


def test_main_returns_non_zero_on_release_error(monkeypatch):
    class FailingManager:
        def release(self, release_type):
            raise release.ReleaseError(f"boom: {release_type}")

    monkeypatch.setattr(release, "ReleaseManager", FailingManager)
    stderr = io.StringIO()
    monkeypatch.setattr(release.sys, "stderr", stderr)

    result = release.main(["patch"])

    assert result == 1
    assert "Release failed: boom: patch" in stderr.getvalue()
