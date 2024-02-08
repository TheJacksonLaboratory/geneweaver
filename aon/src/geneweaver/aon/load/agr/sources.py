"""Download and prepare external source data for Geneweaver AON."""
import requests
import gzip
from typing import Optional
from pathlib import Path


def latest_agr_release() -> str:
    """Get the latest AGR release version.

    :return: The latest AGR release version.
    :raises ValueError: If the latest AGR release version could not be found.
    """
    version = None

    response = requests.get("https://www.alliancegenome.org/api/releaseInfo")
    if response.ok:
        version = response.json().get("releaseVersion")

    if version is None:
        raise ValueError("Could not get the latest AGR release version.")

    return version


def format_agr_orthology_download_url(
    version: str, data_increment: Optional[int] = None
) -> str:
    """Format the AGR orthology download URL.

    :param version: The AGR release version.
    :param data_increment: The data increment (optional).
    :return: The formatted AGR orthology download URL.
    """
    data_increment = 28 if data_increment is None else data_increment
    return (
        f"https://download.alliancegenome.org/{version}/"
        "ORTHOLOGY-ALLIANCE/COMBINED/"
        f"ORTHOLOGY-ALLIANCE_COMBINED_{data_increment}.tsv.gz"
    )


def download_agr_orthology_data(
    download_url: str, download_location: Optional[str] = None
) -> str:
    """Download the latest AGR orthology data.

    :param download_url: The AGR orthology download URL.
    :param download_location: The location to download the AGR orthology data (optional).
    :return: The path to the downloaded AGR orthology data.
    """
    filename = Path(download_url.split("/")[-1])
    response = requests.get(download_url, allow_redirects=True)
    download_file_path = (
        Path(download_location) / filename if download_location else filename
    )
    download_file_path.write_bytes(response.content)
    return str(download_file_path)


def unzip_file(file_path: str, output_location: Optional[str] = None) -> str:
    """Unzip a file.

    :param file_path: The file path to unzip.
    :param output_location: The location to unzip the file (optional).
    :return: The path to the unzipped file.
    """
    file_path = Path(file_path)
    output_location = Path(output_location) if output_location else file_path.parent
    output_file_path = output_location / file_path.stem
    with gzip.open(file_path, "rb") as file:
        with open(output_file_path, "wb") as output_file:
            output_file.write(file.read())

    return str(output_file_path)

