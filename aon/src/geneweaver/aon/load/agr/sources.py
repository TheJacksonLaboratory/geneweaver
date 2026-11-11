"""Download and prepare external source data for Geneweaver AON."""

import gzip
import hashlib
from pathlib import Path
from typing import Optional, Tuple

import requests

FMS_DATAFILE_URL = (
    "https://fms.alliancegenome.org/api/datafile/by/{release}/"
    "ORTHOLOGY-ALLIANCE/COMBINED?latest=true"
)
DOWNLOAD_BASE_URL = "https://download.alliancegenome.org/"


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


def agr_orthology_file(release: str) -> Tuple[str, Optional[str]]:
    """Find a release's combined orthology file through AGR's file service (FMS).

    AGR stores a file under the release that first uploaded it, and later releases
    reuse it: release 9.2.0's file is ``9.0.0/.../ORTHOLOGY-ALLIANCE_COMBINED_13``.
    Guessing ``{release}/..._{n}.tsv.gz`` therefore finds nothing, so FMS is asked
    for the file's actual path.

    :param release: The AGR release version.
    :return: The download URL, and the md5 sum FMS lists (of the *uncompressed*
        file: the .gz's own md5 is S3's ETag), or None if it lists none.
    :raises ValueError: If FMS lists no valid file for the release.
    """
    response = requests.get(FMS_DATAFILE_URL.format(release=release), timeout=60)
    response.raise_for_status()
    files = [f for f in response.json() if f.get("valid") and f.get("s3Path")]
    if not files:
        raise ValueError(f"AGR lists no orthology file for release {release}.")
    newest = max(files, key=lambda f: f.get("uploadDate") or "")
    return DOWNLOAD_BASE_URL + newest["s3Path"], newest.get("md5Sum")


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
    """Download the AGR orthology data.

    An HTTP error raises instead of being saved: a missing file used to be written
    out as S3's XML error page, and only failed later as "Not a gzipped file".

    :param download_url: The AGR orthology download URL.
    :param download_location: The location to download the AGR orthology data.
    :return: The path to the downloaded AGR orthology data.
    """
    filename = Path(download_url.split("/")[-1])
    download_file_path = (
        Path(download_location) / filename if download_location else filename
    )
    with requests.get(
        download_url, allow_redirects=True, stream=True, timeout=300
    ) as response:
        response.raise_for_status()
        with open(download_file_path, "wb") as out:
            for chunk in response.iter_content(chunk_size=1 << 20):
                out.write(chunk)
    return str(download_file_path)


def unzip_file(
    file_path: str,
    output_location: Optional[str] = None,
    md5_sum: Optional[str] = None,
) -> str:
    """Unzip a file, streaming it, and check it against an md5 sum when given.

    :param file_path: The file path to unzip.
    :param output_location: The location to unzip the file (optional).
    :param md5_sum: The expected md5 of the unzipped content (AGR's FMS sum).
    :return: The path to the unzipped file.
    :raises ValueError: If the unzipped content does not match ``md5_sum``.
    """
    file_path = Path(file_path)
    output_location = Path(output_location) if output_location else file_path.parent
    output_file_path = output_location / file_path.stem
    digest = hashlib.md5()  # an integrity check against AGR's sum, not security
    with gzip.open(file_path, "rb") as file:
        with open(output_file_path, "wb") as output_file:
            for chunk in iter(lambda: file.read(1 << 20), b""):
                digest.update(chunk)
                output_file.write(chunk)
    if md5_sum and digest.hexdigest() != md5_sum:
        raise ValueError(
            f"{file_path}: md5 {digest.hexdigest()} does not match AGR's {md5_sum}."
        )

    return str(output_file_path)
