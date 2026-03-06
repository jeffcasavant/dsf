from pathlib import Path
from unittest.mock import MagicMock, patch

from dsf.db import TaskDb
from dsf.worker import process_task


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
