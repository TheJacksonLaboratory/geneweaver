"""CLI to load the database."""

import typer
from rich.progress import Progress

from geneweaver.aon.load.agr import sources
from geneweaver.aon.load.agr import load

from geneweaver.aon.core.database import SessionLocal

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@cli.command()
def agr():
    """Load the Alliance of Genome Resources data."""
    download_msg = "Downloading Alliance of Genome Resources data: "
    with Progress() as progress:

        download = progress.add_task(download_msg+"Determining version", total=100)

        release = sources.latest_agr_release()
        progress.update(download,
                        advance=10,
                        description=download_msg+f"Release: {release}")
        url = sources.format_agr_orthology_download_url(release)

        progress.update(download, advance=2, description=download_msg+"Downloading Data")

        zipped_file = sources.download_agr_orthology_data(url)
        progress.update(download, advance=78, description=download_msg+"Unzipping Data")

        orthology_file = sources.unzip_file(zipped_file)
        progress.update(download, advance=10, description=download_msg+"Complete")

        progress.console.print("Data Downloaded.")

        db_load_msg = "Loading data into the database: "
        db_load = progress.add_task(db_load_msg+"Adding Species", total=1000)

        db = SessionLocal()

        load.init_species(db, orthology_file)
        progress.update(db_load, advance=5, description=db_load_msg+"Adding Algorithms")

        load.add_algorithms(db, orthology_file)
        progress.update(db_load, advance=5, description=db_load_msg+"Adding Genes")

        load.add_genes(db, orthology_file)
        progress.update(db_load, advance=5, description=db_load_msg+"Adding Orthologs")

        for batch in load.get_ortholog_batches(orthology_file, 10000):
            load.add_ortholog_batch(db, batch)
            progress.update(db_load, advance=10)

        progress.update(db_load, description=db_load_msg+"Adding Homology")

        load.add_homology(db)
        progress.update(db_load, advance=70, description=db_load_msg+"Complete")

        progress.console.print("Data Loaded.")

        db.close()
