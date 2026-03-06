from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from dsf.cli import main


def test_submit_with_inline_prompt(tmp_path: Path) -> None:
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
        result = runner.invoke(main, ["submit", "--repo", "jeff/my-app", "--file", str(spec_file)])
    assert result.exit_code == 0
    assert "calm-badger" in result.output
