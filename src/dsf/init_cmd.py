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
