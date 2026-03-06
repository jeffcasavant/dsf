from pathlib import Path
from unittest.mock import MagicMock, patch

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
