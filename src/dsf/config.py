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
