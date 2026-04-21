#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, TextIO


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
UV_LOCK_PATH = REPO_ROOT / "uv.lock"
WORKFLOW_NAME = "Upload Python Package"
PYPI_URL = "https://pypi.org/project/moneywiz-db-api/"
RUN_DISCOVERY_INTERVAL_SECONDS = 5
RUN_DISCOVERY_MAX_ATTEMPTS = 60

PROJECT_SECTION_PATTERN = re.compile(
    r"(?ms)^(?P<header>\[project\]\n)(?P<body>.*?)(?=^\[|\Z)"
)
VERSION_PATTERN = re.compile(
    r'(?m)^(?P<prefix>\s*version\s*=\s*")(?P<version>\d+\.\d+\.\d+)(?P<suffix>".*)$'
)
SCP_REMOTE_PATTERN = re.compile(
    r"^(?P<user>[^@]+)@(?P<host>[^:]+):(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
SleepFn = Callable[[float], None]
WhichFn = Callable[[str], str | None]


class ReleaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    existed: bool
    content: bytes | None

    @classmethod
    def capture(cls, path: Path) -> "FileSnapshot":
        if path.exists():
            return cls(path=path, existed=True, content=path.read_bytes())
        return cls(path=path, existed=False, content=None)

    def restore(self) -> None:
        if self.existed:
            assert self.content is not None
            self.path.write_bytes(self.content)
            return

        if self.path.exists():
            self.path.unlink()


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value.strip())
        if match is None:
            raise ReleaseError(
                f"project.version 必须是稳定三段式版本号，当前值为: {value!r}"
            )
        return cls(*(int(part) for part in match.groups()))

    def bump(self, release_type: str) -> "Version":
        if release_type == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        if release_type == "minor":
            return Version(self.major, self.minor + 1, 0)
        if release_type == "major":
            return Version(self.major + 1, 0, 0)
        raise ReleaseError(f"不支持的发版类型: {release_type}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass
class ReleaseRun:
    database_id: int
    head_sha: str
    status: str
    conclusion: str | None
    url: str

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "ReleaseRun":
        return cls(
            database_id=int(payload["databaseId"]),
            head_sha=str(payload["headSha"]),
            status=str(payload["status"]),
            conclusion=str(payload["conclusion"]) if payload["conclusion"] else None,
            url=str(payload["url"]),
        )


def default_runner(
    args: Sequence[str],
    *,
    cwd: Path,
    capture_output: bool,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        text=True,
        capture_output=capture_output,
    )
    if check and completed.returncode != 0:
        raise ReleaseError(
            f"命令执行失败: {shlex.join(list(args))}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bump version, tag, and publish a GitHub Release."
    )
    parser.add_argument(
        "release_type",
        choices=("patch", "minor", "major"),
        help="Next version bump type.",
    )
    return parser.parse_args(argv)


def read_project_version(pyproject_path: Path) -> Version:
    text = pyproject_path.read_text(encoding="utf-8")
    section_match = PROJECT_SECTION_PATTERN.search(text)
    if section_match is None:
        raise ReleaseError("pyproject.toml 缺少 [project] section")

    version_match = VERSION_PATTERN.search(section_match.group("body"))
    if version_match is None:
        raise ReleaseError("pyproject.toml 缺少 project.version")

    return Version.parse(version_match.group("version"))


def write_project_version(pyproject_path: Path, version: Version) -> None:
    text = pyproject_path.read_text(encoding="utf-8")
    section_match = PROJECT_SECTION_PATTERN.search(text)
    if section_match is None:
        raise ReleaseError("pyproject.toml 缺少 [project] section")

    body = section_match.group("body")
    replacement, count = VERSION_PATTERN.subn(
        lambda match: (
            f"{match.group('prefix')}{version}{match.group('suffix')}"
        ),
        body,
        count=1,
    )
    if count != 1:
        raise ReleaseError("pyproject.toml 中未找到可更新的 project.version")

    updated_text = (
        text[: section_match.start("body")]
        + replacement
        + text[section_match.end("body") :]
    )
    pyproject_path.write_text(updated_text, encoding="utf-8")


def normalize_github_host(host: str) -> str:
    normalized = host.strip().lower().rstrip(".")
    if normalized in {"github.com", "www.github.com", "ssh.github.com"}:
        return "github.com"
    return normalized


def format_github_repo_selector(host: str, owner: str, repo: str) -> str:
    normalized_host = normalize_github_host(host)
    repo_name = repo.removesuffix(".git")
    if not repo_name:
        raise ReleaseError("Git remote 缺少仓库名")
    if normalized_host == "github.com":
        return f"{owner}/{repo_name}"
    return f"{normalized_host}/{owner}/{repo_name}"


def parse_github_repo_selector(
    remote_url: str, *, remote_label: str = "origin push remote"
) -> str:
    normalized = remote_url.strip()
    if not normalized:
        raise ReleaseError(f"{remote_label} 为空，无法确定 GitHub 仓库")

    ssh_match = SCP_REMOTE_PATTERN.fullmatch(normalized)
    if ssh_match is not None:
        return format_github_repo_selector(
            ssh_match.group("host"),
            ssh_match.group("owner"),
            ssh_match.group("repo"),
        )

    parsed = urlparse(normalized)
    if parsed.scheme:
        if parsed.hostname is None:
            raise ReleaseError(f"无法解析 {remote_label}: {remote_url}")
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) < 2:
            raise ReleaseError(f"无法从 {remote_label} 解析仓库: {remote_url}")
        return format_github_repo_selector(
            parsed.hostname,
            path_parts[-2],
            path_parts[-1],
        )

    raise ReleaseError(f"不支持的 {remote_label} 格式: {remote_url}")


class ReleaseManager:
    def __init__(
        self,
        *,
        root: Path = REPO_ROOT,
        pyproject_path: Path = PYPROJECT_PATH,
        uv_lock_path: Path = UV_LOCK_PATH,
        runner: CommandRunner = default_runner,
        sleep_fn: SleepFn = time.sleep,
        which: WhichFn = shutil.which,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
    ) -> None:
        self.root = root
        self.pyproject_path = pyproject_path
        self.uv_lock_path = uv_lock_path
        self.runner = runner
        self.sleep_fn = sleep_fn
        self.which = which
        self.stdout = stdout
        self.stderr = stderr
        self._github_repo: str | None = None

    def release(self, release_type: str) -> None:
        self.ensure_cli_tools()
        self.ensure_on_main_branch()
        self.ensure_clean_worktree()
        self.ensure_github_auth()
        self.sync_remote_state()
        self.ensure_remote_is_not_ahead()

        current_version = read_project_version(self.pyproject_path)
        next_version = current_version.bump(release_type)
        tag_name = f"v{next_version}"

        self.log(f"Preparing release {tag_name} from {current_version}")
        self.ensure_tag_does_not_exist(tag_name)

        self.run_local_preflight(next_version)

        self.run(("git", "add", "pyproject.toml", "uv.lock"))
        self.run(("git", "commit", "-m", f"chore(release): {tag_name}"))

        head_sha = self.run(
            ("git", "rev-parse", "HEAD"), capture_output=True
        ).stdout.strip()
        self.run(("git", "tag", "-a", tag_name, "-m", tag_name))
        self.run(("git", "push", "origin", "main"))
        self.run(("git", "push", "origin", tag_name))

        release_url = self.create_release(tag_name)
        workflow_run = self.wait_for_publish_run(head_sha)

        self.log("")
        self.log("Release completed successfully:")
        self.log(f"- version: {next_version}")
        self.log(f"- tag: {tag_name}")
        self.log(f"- release: {release_url}")
        self.log(f"- workflow: {workflow_run.url}")
        self.log(f"- pypi: {PYPI_URL}")

    def ensure_cli_tools(self) -> None:
        missing_tools = [tool for tool in ("git", "gh", "uv") if self.which(tool) is None]
        if missing_tools:
            missing = ", ".join(missing_tools)
            raise ReleaseError(f"缺少必需命令: {missing}")

    def ensure_on_main_branch(self) -> None:
        branch = self.run(
            ("git", "branch", "--show-current"), capture_output=True
        ).stdout.strip()
        if branch != "main":
            raise ReleaseError(f"只能从 main 发版，当前分支为: {branch or '(detached HEAD)'}")

    def ensure_clean_worktree(self) -> None:
        status = self.run(
            ("git", "status", "--porcelain"), capture_output=True
        ).stdout.strip()
        if status:
            raise ReleaseError("工作区不干净，请先提交或清理改动后再发版")

    def ensure_github_auth(self) -> None:
        self.run(("gh", "auth", "status"))

    def sync_remote_state(self) -> None:
        self.run(("git", "fetch", "origin", "main", "--tags"))

    def ensure_remote_is_not_ahead(self) -> None:
        result = self.run(
            ("git", "rev-list", "--left-right", "--count", "HEAD...origin/main"),
            capture_output=True,
        ).stdout.strip()
        ahead_str, behind_str = result.split()
        behind = int(behind_str)
        if behind > 0:
            raise ReleaseError(
                "origin/main 包含当前本地 main 没有的提交，请先同步后再发版"
            )

    def ensure_tag_does_not_exist(self, tag_name: str) -> None:
        completed = self.run(
            ("git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag_name}"),
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            raise ReleaseError(f"tag 已存在: {tag_name}")

    def run_local_preflight(self, next_version: Version) -> None:
        snapshots = self.capture_release_file_snapshots()
        try:
            write_project_version(self.pyproject_path, next_version)
            self.run(("uv", "lock"))
            self.run_release_checks()
        except Exception:
            self.restore_file_snapshots(snapshots)
            raise

    def run_release_checks(self) -> None:
        self.run(("uv", "run", "ruff", "check", "src/"))
        self.run(("uv", "run", "pytest", "tests/unit", "-v"))
        self.run(("uv", "run", "mypy", "src"))

    def capture_release_file_snapshots(self) -> list[FileSnapshot]:
        return [
            FileSnapshot.capture(self.pyproject_path),
            FileSnapshot.capture(self.uv_lock_path),
        ]

    def restore_file_snapshots(self, snapshots: Sequence[FileSnapshot]) -> None:
        for snapshot in snapshots:
            snapshot.restore()

    def get_github_repo(self) -> str:
        if self._github_repo is None:
            remote_url = self.run(
                ("git", "remote", "get-url", "--push", "origin"),
                capture_output=True,
            ).stdout.strip()
            self._github_repo = parse_github_repo_selector(
                remote_url, remote_label="origin push remote"
            )
        return self._github_repo

    def create_release(self, tag_name: str) -> str:
        repo = self.get_github_repo()
        completed = self.run(
            (
                "gh",
                "release",
                "create",
                tag_name,
                "--repo",
                repo,
                "--title",
                tag_name,
                "--generate-notes",
                "--verify-tag",
            ),
            capture_output=True,
        )
        url = completed.stdout.strip().splitlines()
        if not url:
            raise ReleaseError("GitHub Release 已创建，但未返回 release URL")
        return url[-1]

    def wait_for_publish_run(self, head_sha: str) -> ReleaseRun:
        repo = self.get_github_repo()
        self.log("Waiting for GitHub Actions publish workflow...")
        run: ReleaseRun | None = None

        for _ in range(RUN_DISCOVERY_MAX_ATTEMPTS):
            run = self.find_publish_run(head_sha)
            if run is not None:
                break
            self.sleep_fn(RUN_DISCOVERY_INTERVAL_SECONDS)

        if run is None:
            raise ReleaseError(
                "GitHub Release 已创建，但未找到对应的 Upload Python Package workflow run"
            )

        if run.status != "completed":
            self.run(
                (
                    "gh",
                    "run",
                    "watch",
                    str(run.database_id),
                    "--repo",
                    repo,
                    "--compact",
                    "--exit-status",
                )
            )
            run = self.find_publish_run(head_sha)
            if run is None:
                raise ReleaseError("workflow 已结束，但无法重新读取最终状态")

        if run.conclusion != "success":
            raise ReleaseError(
                "GitHub Release 已创建，但 PyPI 发布 workflow 失败: "
                f"{run.url}"
            )

        return run

    def find_publish_run(self, head_sha: str) -> ReleaseRun | None:
        repo = self.get_github_repo()
        completed = self.run(
            (
                "gh",
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                WORKFLOW_NAME,
                "--event",
                "release",
                "--json",
                "databaseId,headSha,status,conclusion,url",
                "-L",
                "20",
            ),
            capture_output=True,
        )
        payload = json.loads(completed.stdout)
        matches = [
            ReleaseRun.from_payload(item)
            for item in payload
            if str(item["headSha"]) == head_sha
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.database_id)

    def run(
        self,
        args: Sequence[str],
        *,
        capture_output: bool = False,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        self.log(f"+ {shlex.join(list(args))}")
        return self.runner(
            args,
            cwd=self.root,
            capture_output=capture_output,
            check=check,
        )

    def log(self, message: str) -> None:
        print(message, file=self.stdout)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manager = ReleaseManager()
    try:
        manager.release(args.release_type)
    except ReleaseError as exc:
        print(f"Release failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
