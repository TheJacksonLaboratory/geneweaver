"""CLI to load the database."""
import typer
from pathlib import Path
from alembic.config import Config
from alembic import command
from geneweaver.aon.core.config import config

from rich.progress import Progress

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@cli.command()
def version_table() -> bool:
    """Create the database schema."""
    with Progress() as progress:
        db_creation_msg = "Creating database versions table"
        progress.add_task(db_creation_msg, total=None)

        script_location = (Path(__file__).parent.parent / "alembic").resolve()
        alembic_cfg = Config(
            file_=str(script_location / "alembic.ini"),
        )
        alembic_cfg.set_main_option("script_location", str(script_location))
        alembic_cfg.set_main_option("sqlalchemy.url", config.DB.URI)
        command.upgrade(alembic_cfg, "4297df5638d7")

    return True
