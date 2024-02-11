import typer
from geneweaver.aon import __version__
from geneweaver.aon.cli import load

cli = typer.Typer(no_args_is_help=True, rich_markup_mode=True)

cli.add_typer(load.cli, name="load")


def version_callback(version: bool) -> None:
    """Print the version of the GeneWeaver CLI client."""
    if version:
        typer.echo(f"GeneWeaver AON CLI (gwaon) version: {__version__}")
        raise typer.Exit(code=0)


@cli.callback()
def common(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", callback=version_callback),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress all output."),
) -> None:
    """GeneWeaver CLI client."""
    ctx.obj = {"quiet": quiet}
