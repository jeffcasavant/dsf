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
