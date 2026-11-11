"""Test finding and downloading the AGR orthology file."""

import gzip
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from geneweaver.aon.load.agr import sources


def _fms(files: list) -> MagicMock:
    response = MagicMock()
    response.json.return_value = files
    return response


def test_the_file_path_comes_from_fms() -> None:
    """Release 9.2.0 reuses a file uploaded under 9.0.0; FMS gives that path."""
    files = [
        {
            "s3Path": (
                "9.0.0/ORTHOLOGY-ALLIANCE/COMBINED/ORTHOLOGY-ALLIANCE_COMBINED_13.tsv.gz"
            ),
            "md5Sum": "abc",
            "valid": True,
            "uploadDate": "2026-04-05T03:34:59.977+00:00",
        },
        {"s3Path": "8.0.0/old.tsv.gz", "valid": False, "uploadDate": "2027-01-01"},
    ]
    with patch.object(sources.requests, "get", return_value=_fms(files)) as get:
        url, md5 = sources.agr_orthology_file("9.2.0")
    assert "/9.2.0/" in get.call_args.args[0]
    assert url == (
        "https://download.alliancegenome.org/"
        "9.0.0/ORTHOLOGY-ALLIANCE/COMBINED/ORTHOLOGY-ALLIANCE_COMBINED_13.tsv.gz"
    )
    assert md5 == "abc"


def test_no_valid_file_is_an_error() -> None:
    """A release with no file listed fails clearly, before any download."""
    with patch.object(sources.requests, "get", return_value=_fms([])):
        with pytest.raises(ValueError, match="no orthology file"):
            sources.agr_orthology_file("0.0.0")


def _download_response(body: bytes, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [body]
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(str(status))
    return response


def test_an_http_error_raises_instead_of_saving_the_error_page(tmp_path: Path) -> None:
    """S3's XML 404 page was written out and only failed later, at gunzip."""
    page = b"<?xml version='1.0'?><Error>NoSuchKey</Error>"
    with patch.object(
        sources.requests, "get", return_value=_download_response(page, 404)
    ):
        with pytest.raises(requests.HTTPError):
            sources.download_agr_orthology_data("https://x/f.tsv.gz", str(tmp_path))


def test_the_download_is_saved_as_sent(tmp_path: Path) -> None:
    """A successful download is written to disk unchanged."""
    body = gzip.compress(b"data")
    with patch.object(sources.requests, "get", return_value=_download_response(body)):
        path = sources.download_agr_orthology_data("https://x/f.tsv.gz", str(tmp_path))
    assert Path(path).read_bytes() == body


def test_the_unzipped_file_is_checked_against_agrs_md5(tmp_path: Path) -> None:
    """FMS's md5 is of the uncompressed file; a mismatch is refused."""
    content = b"a\tb\n" * 10
    zipped = tmp_path / "f.tsv.gz"
    zipped.write_bytes(gzip.compress(content))
    sources.unzip_file(str(zipped), md5_sum=hashlib.md5(content).hexdigest())
    with pytest.raises(ValueError, match="does not match"):
        sources.unzip_file(str(zipped), md5_sum="0" * 32)


def test_unzip_streams_the_file(tmp_path: Path) -> None:
    """The unzipped file matches, written without reading it all into memory."""
    zipped = tmp_path / "f.tsv.gz"
    zipped.write_bytes(gzip.compress(b"a\tb\n" * 1000))
    out = sources.unzip_file(str(zipped))
    assert Path(out).read_bytes() == b"a\tb\n" * 1000
