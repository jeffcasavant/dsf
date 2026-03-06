from __future__ import annotations

from pathlib import Path

import click

from dsf.db import TaskDb


@click.group()
def main() -> None:
    """Dark Software Factory — automated code generation pipeline."""


@main.command()
def init() -> None:
    """Bootstrap the DSF container and configuration."""
    from dsf.init_cmd import run_init

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
