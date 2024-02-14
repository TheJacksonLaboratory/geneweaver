"""CLI to load the database."""
from pathlib import Path
from typing import Optional

import psycopg
import typer
from geneweaver.aon.core.config import config
from geneweaver.aon.core.database import SessionLocal
from geneweaver.aon.load import agr, geneweaver
from rich.progress import Progress

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@cli.command()
def get_data() -> Path:
    """Get the latest Alliance of Genome Resources data."""
    download_msg = "Downloading Alliance of Genome Resources data: "
    with Progress(transient=True) as progress:
        download = progress.add_task(download_msg + "Determining version", total=None)

        release = agr.sources.latest_agr_release()
        progress.update(download, description=download_msg + f"Release: {release}")
        url = agr.sources.format_agr_orthology_download_url(release)

        progress.update(download, description=download_msg + "Downloading Data")

        zipped_file = agr.sources.download_agr_orthology_data(url)
        progress.update(download, description=download_msg + "Unzipping Data")

        orthology_file = agr.sources.unzip_file(zipped_file)
        progress.update(download, completed=True, description=download_msg + "Complete")


    orthology_file = Path(orthology_file).resolve()

    typer.echo(orthology_file)
    return orthology_file


@cli.command()
def agr(orthology_file: Optional[Path] = None):
    """Load the Alliance of Genome Resources data."""
    if orthology_file is None:
        orthology_file = str(get_data())

    with Progress() as progress:
        db_load_msg = "Loading data into the database: "
        db_load = progress.add_task(db_load_msg + "Adding Species", total=1000)

        db = SessionLocal()

        agr.load.init_species(db, orthology_file)
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

        progress.update(db_load, description=db_load_msg + "Adding Homology")

        progress.console.print("Data Loaded.")

        db.close()


@cli.command()
def gw():
    """Load data from Geneweaver into the AON database."""
    gw_load_msg = "Loading Geneweaver data: "
    with Progress(transient=True) as progress:
        gw_load = progress.add_task(gw_load_msg + "Connecting", total=None)

        db = SessionLocal()

        progress.update(gw_load, description=gw_load_msg + "Adding Species")

        # Species
        geneweaver.species.add_missing_species(db)

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
        with psycopg.connect(config.GW_DB.URI) as gw_connection, psycopg.connect(
            config.DB.URI
        ) as aon_connection:
            with gw_connection.cursor() as gw_cursor, aon_connection.cursor() as aon_cursor:
                homologs = geneweaver.homologs.get_homolog_information(
                    aon_cursor, gw_cursor
                )

        progress.update(gw_load, description=gw_load_msg + "Adding Orthologs")

        geneweaver.homologs.add_missing_orthologs(db, homologs)

        progress.update(gw_load, completed=True, description=gw_load_msg + "Complete")


@cli.command()
def homology():
    with Progress(transient=True) as progress:
        db_load_msg = "Loading data into the database: "
        db_load = progress.add_task(db_load_msg + "Adding Homology", total=None)

        db = SessionLocal()

        agr.load.add_homology(db)

        progress.update(db_load, completed=True, description=db_load_msg + "Complete")
