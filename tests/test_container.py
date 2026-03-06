from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_run_claude_constructs_correct_command(tmp_path: Path) -> None:
    mgr = ContainerManager(
        image_path=Path("/var/lib/machines/dsf-factory"),
        container_name="dsf-factory",
    )
    log_path = tmp_path / "test.log"
    with patch("dsf.container.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        mgr.run_claude(
            workspace="/workspace/my-app",
            prompt="Build a web app",
            gh_token="github_pat_test",
            log_path=log_path,
        )
    cmd_args = mock_run.call_args_list[-1][0][0]
    assert "machinectl" in cmd_args[0] or "systemd-run" in " ".join(cmd_args)
