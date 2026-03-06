from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from dsf.cli import main
from dsf.db import TaskDb


def test_full_submit_status_flow(tmp_path: Path) -> None:
    """Test submit -> status shows the task."""
    db_path = tmp_path / "tasks.db"
    real_db = TaskDb(db_path)

    runner = CliRunner()
    with patch("dsf.cli.TaskDb", return_value=real_db):
        result = runner.invoke(main, ["submit", "--repo", "jeff/test-app", "Build it"])
        assert result.exit_code == 0
        petname = result.output.strip().split("'")[1]

        result = runner.invoke(main, ["status", petname])
        assert result.exit_code == 0
        assert "submitted" in result.output
        assert "test-app" in result.output
