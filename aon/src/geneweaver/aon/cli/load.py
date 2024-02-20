"""CLI to load the database."""
from pathlib import Path
from typing import Optional, Tuple
from argparse import Namespace
import psycopg
import typer
from pathlib import Path
from datetime import datetime
from alembic.config import Config
from alembic import command
from gzip import BadGzipFile
from geneweaver.aon.core.config import config
from geneweaver.aon.core.database import SessionLocal
from geneweaver.aon.core.schema_version import (
    get_schema_version,
    set_up_sessionmanager,
    mark_schema_version_load_complete,
)
from geneweaver.aon.load import agr, geneweaver
from geneweaver.aon.models import Version
from rich.progress import Progress

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@cli.command()
def get_data(release: Optional[str] = None) -> Tuple[str, str]:
    """Get the latest Alliance of Genome Resources data."""
    download_msg = "Downloading Alliance of Genome Resources data: "
    with Progress(transient=True) as progress:
        download = progress.add_task(download_msg + "Determining version", total=None)
        if release is None:
            release = agr.sources.latest_agr_release()

        progress.update(download, description=download_msg + f"Release: {release}")
        data_increment = 28
        still_downloading = True
        while still_downloading:
            try:
                url = agr.sources.format_agr_orthology_download_url(
                    release, data_increment
                )

                progress.update(download, description=download_msg + "Downloading Data")

                zipped_file = agr.sources.download_agr_orthology_data(url)
                progress.update(download, description=download_msg + "Unzipping Data")

                orthology_file = agr.sources.unzip_file(zipped_file)
            except BadGzipFile as e:
                progress.update(download, description=download_msg + f"Error: {e}")
                data_increment = data_increment - 1
                if data_increment < 0:
                    raise e
                continue
            still_downloading = False
        progress.update(download, completed=True, description=download_msg + "Complete")

    orthology_file = Path(orthology_file).resolve()

    typer.echo(orthology_file)
    return str(orthology_file), release


@cli.command()
def agr_release_exists(release: str) -> bool:
    """Check if the Alliance of Genome Resources release exists."""
    db = SessionLocal()
    version = db.query(Version).filter(Version.agr_version == release).first()
    db.close()
    if version:
        print(f"Release {release} exists in the database.")
        return True
    else:
        print(f"Release {release} does not exist in the database.")
        return False


@cli.command()
def create_schema(release) -> Tuple[str, int]:
    """Create the database schema."""
    with Progress() as progress:
        db_creation_msg = "Creating database schema"
        progress.add_task(db_creation_msg, total=None)

        schema_version = release.replace(".", "_")
        timestamp = datetime.now().strftime("%H_%M_%S_%d_%m_%Y")

        schema_name = f"v{schema_version}__{timestamp}"

        script_location = (Path(__file__).parent.parent / "alembic").resolve()
        alembic_cfg = Config(
            file_=str(script_location / "alembic.ini"),
            cmd_opts=Namespace(x=[f"tenant={schema_name}"]),
        )
        alembic_cfg.set_main_option("script_location", str(script_location))
        alembic_cfg.set_main_option("sqlalchemy.url", config.DB.URI)
        command.upgrade(alembic_cfg, "head")

        if agr_release_exists(release):
            raise typer.Exit("Release already exists")

        db = SessionLocal()
        version = Version(
            schema_name=schema_name,
            agr_version=release,
            load_complete=False,
        )
        db.add(version)
        db.commit()
        schema_id = version.id
        db.close()

        print("Created schema: ", schema_name)

        return schema_name, schema_id


def load_agr(orthology_file: str, schema_id: int) -> bool:
    version = get_schema_version(schema_id)
    schema_name = version.schema_name
    session, _ = set_up_sessionmanager(version)

    with Progress() as progress:
        db_load_msg = "Loading AGR data into the database: "
        db_load = progress.add_task(db_load_msg + "Adding Species", total=1000)

        db = session()

        agr.load.init_species(db, orthology_file, schema_name)
        progress.update(
            db_load, advance=5, description=db_load_msg + "Adding Algorithms"
        )

        agr.load.add_algorithms(db, orthology_file)
        progress.update(db_load, advance=5, description=db_load_msg + "Adding Genes")

        agr.load.add_genes(db, orthology_file)
        progress.update(
            db_load, advance=5, description=db_load_msg + "Adding Orthologs"
        )

        for batch in agr.load.get_ortholog_batches(orthology_file, 10000):
            agr.load.add_ortholog_batch(db, batch)
            progress.update(db_load, advance=10)

        progress.console.print("AGR data loaded.")

        db.close()

    return True


@cli.command()
def complete(
    release: Optional[str] = None,
    orthology_file: Optional[Path] = None,
    schema_id: Optional[int] = None,
):
    """Load the Alliance of Genome Resources data."""
    if orthology_file is None:
        orthology_file, release = get_data(release)

    if not schema_id:
        schema_name, schema_id = create_schema(release)

    load_agr(orthology_file, schema_id)

    gw(schema_id)

    homology(schema_id)

    mark_schema_version_load_complete(schema_id)


@cli.command()
def gw(schema_id: int) -> bool:
    """Load data from Geneweaver into the AON database."""
    version = get_schema_version(schema_id)
    schema_name = version.schema_name
    session, _ = set_up_sessionmanager(version)

    gw_load_msg = "Loading Geneweaver data: "
    with Progress(transient=True) as progress:
        gw_load = progress.add_task(gw_load_msg + "Connecting", total=None)

        db = session()

        progress.update(gw_load, description=gw_load_msg + "Adding Genes")

        # Genes
        with psycopg.connect(
            config.GW_DB.URI.replace("postgresql+psycopg", "postgresql")
        ) as connection:
            with connection.cursor() as cursor:
                # Genes
                geneweaver.genes.add_missing_genes(db, cursor)

        progress.update(gw_load, description=gw_load_msg + "Getting Homology")

        # Homologs
        with psycopg.connect(
            config.GW_DB.URI.replace("postgresql+psycopg", "postgresql")
        ) as gw_connection, psycopg.connect(
            config.DB.URI.replace("postgresql+psycopg", "postgresql")
        ) as aon_connection:
            with gw_connection.cursor() as gw_cursor, aon_connection.cursor() as aon_cursor:
                homologs = geneweaver.homologs.get_homolog_information(
                    aon_cursor, gw_cursor, aon_schema_name=schema_name
                )

        progress.update(gw_load, description=gw_load_msg + "Adding Orthologs")

        geneweaver.homologs.add_missing_orthologs(db, homologs)

        progress.update(gw_load, completed=True, description=gw_load_msg + "Complete")

    return True


@cli.command()
def homology(schema_id: int) -> bool:
    version = get_schema_version(schema_id)
    session, _ = set_up_sessionmanager(version)

    with Progress(transient=True) as progress:
        db_load_msg = "Loading data into the database: "
        db_load = progress.add_task(db_load_msg + "Adding Homology", total=None)

        db = session()

        agr.load.add_homology(db)

        progress.update(db_load, completed=True, description=db_load_msg + "Complete")

        db.close()

    return True
