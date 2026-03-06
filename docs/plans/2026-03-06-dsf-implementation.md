# DSF Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an automated code generation pipeline that runs Claude Code inside a systemd-nspawn container, with tasks submitted via CLI and results pushed to GitHub.

**Architecture:** Python CLI (`dsf`) orchestrates a persistent systemd-nspawn Arch container. Tasks are stored in SQLite, processed by a polling worker daemon that shells into the container to run Claude Code with `--dangerously-skip-permissions`. Output is committed and pushed to GitHub.

**Tech Stack:** Python 3.12+, UV, click, SQLite, systemd-nspawn/machinectl, petname, ruff, mypy

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/dsf/__init__.py`
- Create: `src/dsf/cli.py`

**Step 1: Initialize UV project**

Run:
```bash
cd /home/jeff/projects/dsf
uv init --lib --name dsf
```

**Step 2: Configure pyproject.toml**

Replace the generated `pyproject.toml` with:

```toml
[project]
name = "dsf"
version = "0.1.0"
description = "Dark Software Factory — automated code generation pipeline"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1",
    "petname>=2.6",
]

[project.scripts]
dsf = "dsf.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "SIM", "TCH"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
```

**Step 3: Create minimal CLI entry point**

`src/dsf/__init__.py`:
```python
"""Dark Software Factory."""
```

`src/dsf/cli.py`:
```python
import click


@click.group()
def main() -> None:
    """Dark Software Factory — automated code generation pipeline."""


@main.command()
def init() -> None:
    """Bootstrap the DSF container and configuration."""
    click.echo("dsf init: not yet implemented")


@main.command()
def worker() -> None:
    """Start the worker daemon."""
    click.echo("dsf worker: not yet implemented")


@main.command()
def destroy() -> None:
    """Tear down the DSF container."""
    click.echo("dsf destroy: not yet implemented")
```

**Step 4: Install and verify**

Run:
```bash
uv sync
uv run dsf --help
```
Expected: Help text showing `init`, `worker`, `destroy` commands.

**Step 5: Commit**

```bash
git add pyproject.toml src/ uv.lock
git commit -m "feat: scaffold dsf project with UV and click CLI"
```

---

### Task 2: Config Module

**Files:**
- Create: `src/dsf/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
import tomllib
from pathlib import Path
from dsf.config import DsfConfig, load_config, save_config


def test_load_config_creates_default(tmp_path: Path) -> None:
    config = load_config(config_dir=tmp_path)
    assert config.github_token == ""
    assert config.container_name == "dsf-factory"
    assert config.image_path == Path("/var/lib/machines/dsf-factory")
    assert config.poll_interval == 5


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    config = DsfConfig(
        github_token="github_pat_test123",
        container_name="dsf-factory",
        image_path=Path("/var/lib/machines/dsf-factory"),
        poll_interval=10,
    )
    save_config(config, config_dir=tmp_path)

    config_file = tmp_path / "config.toml"
    assert config_file.exists()

    loaded = load_config(config_dir=tmp_path)
    assert loaded.github_token == "github_pat_test123"
    assert loaded.poll_interval == 10
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dsf.config'`

**Step 3: Write minimal implementation**

`src/dsf/config.py`:
```python
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".dsf"


@dataclass
class DsfConfig:
    github_token: str = ""
    container_name: str = "dsf-factory"
    image_path: Path = field(default_factory=lambda: Path("/var/lib/machines/dsf-factory"))
    poll_interval: int = 5


def load_config(config_dir: Path = DEFAULT_CONFIG_DIR) -> DsfConfig:
    config_file = config_dir / "config.toml"
    if not config_file.exists():
        return DsfConfig()

    with open(config_file, "rb") as f:
        data = tomllib.load(f)

    return DsfConfig(
        github_token=data.get("github", {}).get("token", ""),
        container_name=data.get("container", {}).get("name", "dsf-factory"),
        image_path=Path(
            data.get("container", {}).get("image_path", "/var/lib/machines/dsf-factory")
        ),
        poll_interval=data.get("worker", {}).get("poll_interval", 5),
    )


def save_config(config: DsfConfig, config_dir: Path = DEFAULT_CONFIG_DIR) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    content = f"""\
[github]
token = "{config.github_token}"

[container]
name = "{config.container_name}"
image_path = "{config.image_path}"

[worker]
poll_interval = {config.poll_interval}
"""
    config_file.write_text(content)
```

**Step 4: Add pytest dependency and run tests**

Run:
```bash
uv add --dev pytest
uv run pytest tests/test_config.py -v
```
Expected: 2 tests PASS.

**Step 5: Commit**

```bash
git add src/dsf/config.py tests/test_config.py pyproject.toml uv.lock
git commit -m "feat: add config module with TOML load/save"
```

---

### Task 3: Database Module

**Files:**
- Create: `src/dsf/db.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path
from dsf.db import TaskDb, TaskStatus


def test_create_and_get_task(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petname = db.create_task(name="my-app", prompt="Build a web app", github_repo="jeff/my-app")
    task = db.get_task(petname)
    assert task is not None
    assert task["name"] == "my-app"
    assert task["prompt"] == "Build a web app"
    assert task["github_repo"] == "jeff/my-app"
    assert task["status"] == "submitted"


def test_list_tasks(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    db.create_task(name="app1", prompt="Build app 1", github_repo="jeff/app1")
    db.create_task(name="app2", prompt="Build app 2", github_repo="jeff/app2")
    tasks = db.list_tasks()
    assert len(tasks) == 2


def test_claim_next_task(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    db.create_task(name="app1", prompt="Build app 1", github_repo="jeff/app1")
    task = db.claim_next()
    assert task is not None
    assert task["status"] == "running"
    assert task["started_at"] is not None
    # No more tasks to claim
    assert db.claim_next() is None


def test_complete_task(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petname = db.create_task(name="app1", prompt="Build app 1", github_repo="jeff/app1")
    db.claim_next()
    db.update_status(petname, TaskStatus.COMPLETED)
    task = db.get_task(petname)
    assert task is not None
    assert task["status"] == "completed"
    assert task["completed_at"] is not None


def test_fail_task(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petname = db.create_task(name="app1", prompt="Build app 1", github_repo="jeff/app1")
    db.claim_next()
    db.update_status(petname, TaskStatus.FAILED, error="something broke")
    task = db.get_task(petname)
    assert task is not None
    assert task["status"] == "failed"
    assert task["error"] == "something broke"


def test_petnames_are_unique(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petnames = set()
    for i in range(20):
        pn = db.create_task(name=f"app{i}", prompt=f"Build app {i}", github_repo=f"jeff/app{i}")
        petnames.add(pn)
    assert len(petnames) == 20
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dsf.db'`

**Step 3: Write minimal implementation**

`src/dsf/db.py`:
```python
from __future__ import annotations

import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any

import petname as petname_lib

DEFAULT_DB_PATH = Path.home() / ".dsf" / "tasks.db"

SCHEMA = """\
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY,
    petname      TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    prompt       TEXT NOT NULL,
    github_repo  TEXT,
    status       TEXT DEFAULT 'submitted',
    error        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    started_at   TEXT,
    completed_at TEXT
);
"""


class TaskStatus(StrEnum):
    SUBMITTED = "submitted"
    RUNNING = "running"
    PUSHING = "pushing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskDb:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def _generate_petname(self) -> str:
        for _ in range(100):
            name: str = petname_lib.generate(words=2, separator="-")
            row = self.conn.execute(
                "SELECT 1 FROM tasks WHERE petname = ?", (name,)
            ).fetchone()
            if row is None:
                return name
        raise RuntimeError("Failed to generate unique petname after 100 attempts")

    def create_task(self, name: str, prompt: str, github_repo: str) -> str:
        pn = self._generate_petname()
        self.conn.execute(
            "INSERT INTO tasks (petname, name, prompt, github_repo) VALUES (?, ?, ?, ?)",
            (pn, name, prompt, github_repo),
        )
        self.conn.commit()
        return pn

    def get_task(self, petname: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE petname = ?", (petname,)
        ).fetchone()
        return dict(row) if row else None

    def list_tasks(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def claim_next(self) -> dict[str, Any] | None:
        row = self.conn.execute(
            "UPDATE tasks SET status = 'running', started_at = datetime('now') "
            "WHERE id = (SELECT id FROM tasks WHERE status = 'submitted' ORDER BY created_at LIMIT 1) "
            "RETURNING *"
        ).fetchone()
        self.conn.commit()
        return dict(row) if row else None

    def update_status(
        self, petname: str, status: TaskStatus, error: str | None = None
    ) -> None:
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            self.conn.execute(
                "UPDATE tasks SET status = ?, error = ?, completed_at = datetime('now') WHERE petname = ?",
                (status.value, error, petname),
            )
        else:
            self.conn.execute(
                "UPDATE tasks SET status = ?, error = ? WHERE petname = ?",
                (status.value, error, petname),
            )
        self.conn.commit()
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_db.py -v`
Expected: 6 tests PASS.

**Step 5: Commit**

```bash
git add src/dsf/db.py tests/test_db.py
git commit -m "feat: add SQLite task database with petname IDs"
```

---

### Task 4: Container Module

**Files:**
- Create: `src/dsf/container.py`
- Create: `tests/test_container.py`

**Step 1: Write the failing tests**

These tests mock subprocess calls since we can't run nspawn in test:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
from dsf.container import ContainerManager


def test_bootstrap_runs_pacstrap(tmp_path: Path) -> None:
    mgr = ContainerManager(image_path=tmp_path / "machine")
    with patch("dsf.container.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        mgr.bootstrap()
    calls = [str(c) for c in mock_run.call_args_list]
    assert any("pacstrap" in c for c in calls)


def test_is_running_checks_machinectl() -> None:
    mgr = ContainerManager(image_path=Path("/var/lib/machines/dsf-factory"))
    with patch("dsf.container.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="dsf-factory\n")
        assert mgr.is_running() is True


def test_run_claude_constructs_correct_command() -> None:
    mgr = ContainerManager(
        image_path=Path("/var/lib/machines/dsf-factory"),
        container_name="dsf-factory",
    )
    with patch("dsf.container.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        mgr.run_claude(
            workspace="/workspace/my-app",
            prompt="Build a web app",
            gh_token="github_pat_test",
            log_path=Path("/tmp/test.log"),
        )
    cmd_args = mock_run.call_args_list[-1][0][0]
    assert "machinectl" in cmd_args[0] or "systemd-run" in " ".join(cmd_args)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_container.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

`src/dsf/container.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path

DEFAULT_IMAGE_PATH = Path("/var/lib/machines/dsf-factory")
CONTAINER_PACKAGES = ["base", "base-devel", "git", "github-cli", "nodejs", "npm"]


class ContainerManager:
    def __init__(
        self,
        image_path: Path = DEFAULT_IMAGE_PATH,
        container_name: str = "dsf-factory",
    ) -> None:
        self.image_path = image_path
        self.container_name = container_name

    def bootstrap(self) -> None:
        """Create the container rootfs with pacstrap."""
        self.image_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["pacstrap", "-c", str(self.image_path)] + CONTAINER_PACKAGES,
            check=True,
        )
        # Install Claude Code inside the container
        subprocess.run(
            [
                "systemd-nspawn",
                "-D", str(self.image_path),
                "npm", "install", "-g", "@anthropic-ai/claude-code",
            ],
            check=True,
        )
        # Create worker user
        subprocess.run(
            [
                "systemd-nspawn",
                "-D", str(self.image_path),
                "useradd", "-m", "-s", "/bin/bash", "worker",
            ],
            check=True,
        )

    def start(self, claude_dir: Path, workspace_dir: Path) -> None:
        """Boot the container with bind mounts."""
        workspace_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "systemd-nspawn",
                "--boot",
                "--machine", self.container_name,
                "-D", str(self.image_path),
                f"--bind-ro={claude_dir}:/home/worker/.claude",
                f"--bind={workspace_dir}:/workspace",
            ],
            check=True,
        )

    def stop(self) -> None:
        """Shutdown the container."""
        subprocess.run(
            ["machinectl", "terminate", self.container_name],
            check=True,
        )

    def is_running(self) -> bool:
        """Check if the container is currently running."""
        result = subprocess.run(
            ["machinectl", "list", "--no-legend", "--no-pager"],
            capture_output=True,
            text=True,
        )
        return self.container_name in result.stdout

    def run_claude(
        self,
        workspace: str,
        prompt: str,
        gh_token: str,
        log_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        """Run Claude Code inside the container for a task."""
        cmd = [
            "machinectl", "shell",
            f"--setenv=GH_TOKEN={gh_token}",
            f"--setenv=HOME=/home/worker",
            f"worker@{self.container_name}",
            "/usr/bin/bash", "-c",
            f"cd {workspace} && claude --dangerously-skip-permissions -p {_shell_quote(prompt)}",
        ]
        with open(log_path, "w") as log_file:
            result = subprocess.run(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
        return result

    def exec_shell(self, command: str) -> subprocess.CompletedProcess[str]:
        """Run an arbitrary command in the container as worker."""
        return subprocess.run(
            [
                "machinectl", "shell",
                f"worker@{self.container_name}",
                "/usr/bin/bash", "-c", command,
            ],
            capture_output=True,
            text=True,
        )

    def destroy(self) -> None:
        """Remove the container image."""
        if self.is_running():
            self.stop()
        subprocess.run(["rm", "-rf", str(self.image_path)], check=True)


def _shell_quote(s: str) -> str:
    """Single-quote a string for shell use."""
    return "'" + s.replace("'", "'\\''") + "'"
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_container.py -v`
Expected: 3 tests PASS.

**Step 5: Commit**

```bash
git add src/dsf/container.py tests/test_container.py
git commit -m "feat: add container module for nspawn lifecycle management"
```

---

### Task 5: Init Command

**Files:**
- Modify: `src/dsf/cli.py`
- Create: `src/dsf/init_cmd.py`
- Create: `tests/test_init_cmd.py`

**Step 1: Write the failing test**

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from dsf.cli import main


def test_init_prompts_for_token_and_bootstraps(tmp_path: Path) -> None:
    runner = CliRunner()
    with (
        patch("dsf.init_cmd.ContainerManager") as mock_cm_cls,
        patch("dsf.init_cmd.save_config") as mock_save,
        patch("dsf.init_cmd.DEFAULT_CONFIG_DIR", tmp_path),
    ):
        mock_cm = MagicMock()
        mock_cm_cls.return_value = mock_cm
        result = runner.invoke(main, ["init"], input="github_pat_test123\n")
    assert result.exit_code == 0
    mock_cm.bootstrap.assert_called_once()
    mock_save.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_init_cmd.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/dsf/init_cmd.py`:
```python
from __future__ import annotations

import click

from dsf.config import DEFAULT_CONFIG_DIR, DsfConfig, load_config, save_config
from dsf.container import ContainerManager


def run_init() -> None:
    """Bootstrap the DSF container and create configuration."""
    config = load_config()

    token = click.prompt(
        "GitHub fine-grained PAT (scoped to target repos)",
        default=config.github_token or "",
        show_default=bool(config.github_token),
    )

    config = DsfConfig(github_token=token)
    save_config(config)
    click.echo(f"Config saved to {DEFAULT_CONFIG_DIR / 'config.toml'}")

    click.echo(f"Bootstrapping container at {config.image_path}...")
    mgr = ContainerManager(image_path=config.image_path, container_name=config.container_name)
    mgr.bootstrap()
    click.echo("Container bootstrapped successfully.")
```

Update `src/dsf/cli.py` — replace the `init` command:

```python
import click

from dsf.init_cmd import run_init


@click.group()
def main() -> None:
    """Dark Software Factory — automated code generation pipeline."""


@main.command()
def init() -> None:
    """Bootstrap the DSF container and configuration."""
    run_init()


@main.command()
def worker() -> None:
    """Start the worker daemon."""
    click.echo("dsf worker: not yet implemented")


@main.command()
def destroy() -> None:
    """Tear down the DSF container."""
    click.echo("dsf destroy: not yet implemented")
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_init_cmd.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dsf/init_cmd.py src/dsf/cli.py tests/test_init_cmd.py
git commit -m "feat: implement dsf init command with token prompt and container bootstrap"
```

---

### Task 6: Submit Command

**Files:**
- Modify: `src/dsf/cli.py`
- Create: `tests/test_submit.py`

**Step 1: Write the failing test**

```python
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from dsf.cli import main


def test_submit_with_inline_prompt(tmp_path: Path) -> None:
    db_path = tmp_path / "tasks.db"
    runner = CliRunner()
    with patch("dsf.cli.TaskDb") as mock_db_cls:
        mock_db = mock_db_cls.return_value
        mock_db.create_task.return_value = "swift-otter"
        result = runner.invoke(main, ["submit", "--repo", "jeff/my-app", "Build a web app"])
    assert result.exit_code == 0
    assert "swift-otter" in result.output
    mock_db.create_task.assert_called_once()


def test_submit_with_file(tmp_path: Path) -> None:
    spec_file = tmp_path / "spec.md"
    spec_file.write_text("# Build a web app\nWith authentication.")
    runner = CliRunner()
    with patch("dsf.cli.TaskDb") as mock_db_cls:
        mock_db = mock_db_cls.return_value
        mock_db.create_task.return_value = "calm-badger"
        result = runner.invoke(
            main, ["submit", "--repo", "jeff/my-app", "--file", str(spec_file)]
        )
    assert result.exit_code == 0
    assert "calm-badger" in result.output
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_submit.py -v`
Expected: FAIL

**Step 3: Add submit command to cli.py**

Add to `src/dsf/cli.py`:

```python
import click
from pathlib import Path

from dsf.db import TaskDb
from dsf.init_cmd import run_init


@click.group()
def main() -> None:
    """Dark Software Factory — automated code generation pipeline."""


@main.command()
def init() -> None:
    """Bootstrap the DSF container and configuration."""
    run_init()


@main.command()
@click.argument("prompt", required=False)
@click.option("--repo", required=True, help="GitHub repo (e.g. jeff/my-app)")
@click.option("--file", "file_path", type=click.Path(exists=True), help="Read prompt from file")
def submit(prompt: str | None, repo: str, file_path: str | None) -> None:
    """Submit a task to the factory."""
    if file_path:
        prompt = Path(file_path).read_text()
    if not prompt:
        raise click.UsageError("Provide a prompt string or --file")

    db = TaskDb()
    petname = db.create_task(name=repo.split("/")[-1], prompt=prompt, github_repo=repo)
    click.echo(f"Task '{petname}' submitted")


@main.command()
@click.argument("petname", required=False)
def status(petname: str | None) -> None:
    """Show task status."""
    db = TaskDb()
    if petname:
        task = db.get_task(petname)
        if not task:
            raise click.ClickException(f"Task '{petname}' not found")
        click.echo(f"{task['petname']}  {task['status']}  {task['name']}  {task['github_repo']}")
        if task["error"]:
            click.echo(f"  Error: {task['error']}")
    else:
        tasks = db.list_tasks()
        if not tasks:
            click.echo("No tasks.")
            return
        for t in tasks:
            click.echo(f"{t['petname']:20s} {t['status']:12s} {t['name']}")


@main.command()
@click.argument("petname")
def logs(petname: str) -> None:
    """Show logs for a task."""
    from dsf.config import DEFAULT_CONFIG_DIR

    log_path = DEFAULT_CONFIG_DIR / "logs" / f"task-{petname}.log"
    if not log_path.exists():
        raise click.ClickException(f"No logs found for '{petname}'")
    click.echo(log_path.read_text())


@main.command()
def worker() -> None:
    """Start the worker daemon."""
    from dsf.worker import run_worker

    run_worker()


@main.command()
def destroy() -> None:
    """Tear down the DSF container."""
    from dsf.config import load_config
    from dsf.container import ContainerManager

    config = load_config()
    mgr = ContainerManager(image_path=config.image_path, container_name=config.container_name)
    mgr.destroy()
    click.echo("Container destroyed.")
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_submit.py -v`
Expected: 2 tests PASS.

**Step 5: Commit**

```bash
git add src/dsf/cli.py tests/test_submit.py
git commit -m "feat: implement submit, status, logs, destroy CLI commands"
```

---

### Task 7: Worker Daemon

**Files:**
- Create: `src/dsf/worker.py`
- Create: `tests/test_worker.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
from dsf.worker import process_task
from dsf.db import TaskDb


def test_process_task_success(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petname = db.create_task(name="my-app", prompt="Build it", github_repo="jeff/my-app")
    task = db.claim_next()
    assert task is not None

    mock_container = MagicMock()
    mock_container.run_claude.return_value = MagicMock(returncode=0)
    mock_container.exec_shell.return_value = MagicMock(returncode=0)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    workspace_dir = tmp_path / "workspaces"

    with patch("dsf.worker.load_config") as mock_cfg:
        mock_cfg.return_value = MagicMock(github_token="tok", poll_interval=1)
        process_task(
            db=db,
            task=task,
            container=mock_container,
            log_dir=log_dir,
            workspace_dir=workspace_dir,
        )

    updated = db.get_task(petname)
    assert updated is not None
    assert updated["status"] == "completed"


def test_process_task_claude_failure(tmp_path: Path) -> None:
    db = TaskDb(tmp_path / "tasks.db")
    petname = db.create_task(name="my-app", prompt="Build it", github_repo="jeff/my-app")
    task = db.claim_next()
    assert task is not None

    mock_container = MagicMock()
    mock_container.run_claude.return_value = MagicMock(returncode=1)
    mock_container.exec_shell.return_value = MagicMock(returncode=0)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    workspace_dir = tmp_path / "workspaces"

    with patch("dsf.worker.load_config") as mock_cfg:
        mock_cfg.return_value = MagicMock(github_token="tok", poll_interval=1)
        process_task(
            db=db,
            task=task,
            container=mock_container,
            log_dir=log_dir,
            workspace_dir=workspace_dir,
        )

    updated = db.get_task(petname)
    assert updated is not None
    assert updated["status"] == "failed"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_worker.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/dsf/worker.py`:
```python
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from dsf.config import DEFAULT_CONFIG_DIR, load_config
from dsf.container import ContainerManager
from dsf.db import TaskDb, TaskStatus

logger = logging.getLogger("dsf.worker")


def process_task(
    db: TaskDb,
    task: dict[str, Any],
    container: ContainerManager,
    log_dir: Path,
    workspace_dir: Path,
) -> None:
    """Process a single claimed task."""
    config = load_config()
    petname = task["petname"]
    name = task["name"]
    log_path = log_dir / f"task-{petname}.log"

    workspace = f"/workspace/{name}"
    host_workspace = workspace_dir / name
    host_workspace.mkdir(parents=True, exist_ok=True)

    try:
        # Init git repo and set remote
        container.exec_shell(f"mkdir -p {workspace} && cd {workspace} && git init")
        container.exec_shell(
            f"cd {workspace} && git remote add origin https://github.com/{task['github_repo']}.git"
        )

        # Run Claude Code
        result = container.run_claude(
            workspace=workspace,
            prompt=task["prompt"],
            gh_token=config.github_token,
            log_path=log_path,
        )

        if result.returncode != 0:
            db.update_status(petname, TaskStatus.FAILED, error=f"Claude exited with code {result.returncode}")
            logger.error("Task %s failed: Claude exit code %d", petname, result.returncode)
            return

        # Push to GitHub
        db.update_status(petname, TaskStatus.PUSHING)
        container.exec_shell(f"cd {workspace} && git add -A && git commit -m 'DSF: {name}' --allow-empty")
        push_result = container.exec_shell(
            f"cd {workspace} && git push -u origin HEAD"
        )

        if push_result.returncode != 0:
            db.update_status(petname, TaskStatus.FAILED, error=f"Push failed: {push_result.stderr}")
            logger.error("Task %s push failed: %s", petname, push_result.stderr)
            return

        db.update_status(petname, TaskStatus.COMPLETED)
        logger.info("Task %s completed successfully", petname)

    except Exception as e:
        db.update_status(petname, TaskStatus.FAILED, error=str(e))
        logger.exception("Task %s failed with exception", petname)


def run_worker() -> None:
    """Main worker loop — polls DB for tasks and processes them."""
    config = load_config()
    log_dir = DEFAULT_CONFIG_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir = DEFAULT_CONFIG_DIR / "workspaces"

    logging.basicConfig(
        filename=str(log_dir / "worker.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = TaskDb()
    container = ContainerManager(
        image_path=config.image_path,
        container_name=config.container_name,
    )

    if not container.is_running():
        logger.info("Starting container %s", config.container_name)
        container.start(
            claude_dir=Path.home() / ".claude",
            workspace_dir=workspace_dir,
        )

    logger.info("Worker started, polling every %ds", config.poll_interval)

    while True:
        task = db.claim_next()
        if task:
            logger.info("Claimed task %s (%s)", task["petname"], task["name"])
            process_task(
                db=db,
                task=task,
                container=container,
                log_dir=log_dir,
                workspace_dir=workspace_dir,
            )
        else:
            time.sleep(config.poll_interval)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_worker.py -v`
Expected: 2 tests PASS.

**Step 5: Commit**

```bash
git add src/dsf/worker.py tests/test_worker.py
git commit -m "feat: implement worker daemon with task processing loop"
```

---

### Task 8: Integration Test & Lint Pass

**Files:**
- Create: `tests/test_cli_integration.py`
- Modify: various (lint fixes)

**Step 1: Write CLI integration test**

```python
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from pathlib import Path
from dsf.cli import main


def test_full_submit_status_flow(tmp_path: Path) -> None:
    """Test submit → status shows the task."""
    db_path = tmp_path / "tasks.db"
    with patch("dsf.cli.TaskDb") as mock_cls:
        from dsf.db import TaskDb
        real_db = TaskDb(db_path)
        mock_cls.return_value = real_db

        runner = CliRunner()

        result = runner.invoke(main, ["submit", "--repo", "jeff/test-app", "Build it"])
        assert result.exit_code == 0
        petname = result.output.strip().split("'")[1]

        result = runner.invoke(main, ["status", petname])
        assert result.exit_code == 0
        assert "submitted" in result.output
        assert "test-app" in result.output
```

**Step 2: Run test**

Run: `uv run pytest tests/test_cli_integration.py -v`
Expected: PASS

**Step 3: Run linting and type checks**

Run:
```bash
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/
uv run mypy src/dsf/
```

Fix any issues reported.

**Step 4: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add integration test, fix lint and type issues"
```

---

### Task 9: End-to-End Manual Test

**Files:** None (manual verification)

**Step 1: Install dsf globally**

Run:
```bash
uv tool install -e .
dsf --help
```
Expected: CLI help with all subcommands.

**Step 2: Bootstrap container (requires sudo)**

Run:
```bash
sudo dsf init
```
Follow prompts: enter GitHub PAT when asked.
Expected: Container bootstrapped at `/var/lib/machines/dsf-factory`.

**Step 3: Submit a test task**

Run:
```bash
dsf submit --repo jeff/dsf-test "Create a simple Python hello world script with a README"
```
Expected: Task petname printed.

**Step 4: Start worker and observe**

Run:
```bash
sudo dsf worker
```
Expected: Worker picks up task, runs Claude Code inside container, pushes to GitHub.

**Step 5: Check status and logs**

Run:
```bash
dsf status
dsf logs <petname>
```
Expected: Task shows as completed, logs show Claude Code output.
