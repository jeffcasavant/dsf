import click


@click.group()
def main() -> None:
    """Dark Software Factory — automated code generation pipeline."""


@main.command()
def init() -> None:
    """Bootstrap the DSF container and configuration."""
    from dsf.init_cmd import run_init

    run_init()


@main.command()
def worker() -> None:
    """Start the worker daemon."""
    click.echo("dsf worker: not yet implemented")


@main.command()
def destroy() -> None:
    """Tear down the DSF container."""
    click.echo("dsf destroy: not yet implemented")
