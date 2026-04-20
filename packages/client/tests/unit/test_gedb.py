import time

import numpy
import pytest
from geneweaver.client.gedb import (
    DataRequest,
    DataResult,
    GeneExpressionDatabaseClient,
    Metadata,
    Sex,
    SourceType,
    StrainResult,
)
from numpy.random import Generator
from pandas import DataFrame
from requests.exceptions import HTTPError


class TestOrthologs:
    """Test Orthologs.

    A very basic test class which should be improved to
    include more error conditions.
    """

    def test_init_client_no_args(self) -> None:
        """Test client no args."""
        client = GeneExpressionDatabaseClient()
        assert client is not None, "Unexpectedly cannot make a client with no args"

    def test_init_client_on_dev(self):
        """Test client on dev."""
        client = GeneExpressionDatabaseClient("https://geneweaver-dev.jax.org/gedb")
        assert client is not None, "Unexpectedly cannot make a client with dev uri"

    def test_get_tissues(self, test_client: GeneExpressionDatabaseClient):
        """Test get tissues."""
        tissues: set[str] = test_client.distinct("tissue")
        assert "heart" in tissues, "Tissue set must contain heart"
        assert "striatum" in tissues, "Tissue set must contain striatum"

    def test_get_strains(self, test_client: GeneExpressionDatabaseClient):
        """Test get strains."""
        tissues: set[str] = test_client.distinct("strain")
        assert "C57BL/6J" in tissues, "Strains set must contain C57BL/6J"
        assert "A/J" in tissues, "Strains set must contain A/J"

    def test_get_not_there(self, test_client: GeneExpressionDatabaseClient):
        """Test not there."""
        with pytest.raises(HTTPError):
            test_client.distinct("NOT-THERE")

    def test_search_expressions(self, test_client: GeneExpressionDatabaseClient):
        """Test get tissues."""
        imputations = self._connective_tissue_disorder(test_client)
        assert len(imputations) == 16425, (
            f"The length of the imputations array is {len(imputations)}"
        )

    def test_search_strain_expressions(self, test_client: GeneExpressionDatabaseClient):
        """Test get tissues."""
        result: list[StrainResult] = self._connective_tissue_disorder_expressions(test_client)
        assert len(result) == 657, f"The length of the imputations array is {len(result)}"

    def test_sort_results_by_strain(self, test_client: GeneExpressionDatabaseClient):
        """Test sort results."""
        imputations = self._connective_tissue_disorder(test_client)
        srtd = test_client.sort_by_field("strain", imputations)
        # There are 657 strains in this list of results.
        assert len(srtd) == 657, f"The size of the strains map is {len(srtd)}"

    def test_expression_results(self, test_client: GeneExpressionDatabaseClient):
        """Test sort results into form used by recommender code."""
        strain_expressions: list[StrainResult] = self._connective_tissue_disorder_expressions(
            test_client
        )

        data_dict = {sr.strain: sr for sr in strain_expressions}

        # By strain=C57BL/6J and indiv_name=s1 should give example table.
        c57_strain: DataFrame = test_client.frame(data_dict, "C57BL/6J", "s1", Sex.Female)
        assert len(c57_strain) == 25, f"The size of the frame is {len(c57_strain)}"

        # By strain=BALB/cByJ and indiv_name=s8 should give example table.
        balb_frame: DataFrame = test_client.frame(data_dict, "BALB/cByJ", "s8", Sex.Female)
        assert len(balb_frame) == 25, f"The size of the frame is {len(balb_frame)}"

        # By strain=BXD24/TyJ and indiv_name=s147 should give example table.
        bxd_frame: DataFrame = test_client.frame(data_dict, "BXH8/TyJ", "s1752", Sex.Both)
        assert len(bxd_frame) == 25, f"The size of the frame is {len(bxd_frame)}"

    def test_random_results1(self, test_client: GeneExpressionDatabaseClient):
        """Generate random expression results to be used in rho calculation."""
        metas: list[Metadata] = test_client.get_meta("maxilla")
        ingest_id: str = metas[0].ingestid
        rand1: list[DataFrame] = test_client.random(ingest_id, 25)
        assert len(rand1) == 1, f"The number of frames is {len(rand1)}"
        assert len(rand1[0]) == 25, f"The size of the frame is {len(rand1[0])}"

    def test_random_results2(self, test_client: GeneExpressionDatabaseClient):
        """Generate random expression results to be used in rho calculation."""
        metas: list[Metadata] = test_client.get_meta("maxilla")
        ingest_id: str = metas[0].ingestid
        rand1: list[DataFrame] = test_client.random(ingest_id, 5, 5)
        assert len(rand1) == 5, f"The number of frames is {len(rand1)}"
        assert len(rand1[0]) == 5, f"The size of the frame is {len(rand1[0])}"

    def test_random_results3(self, test_client: GeneExpressionDatabaseClient):
        """Generate random expression results to be used in rho calculation."""
        metas: list[Metadata] = test_client.get_meta("maxilla")
        ingest_id: str = metas[0].ingestid
        rand1: list[DataFrame] = test_client.random(ingest_id, 4, 100)
        assert len(rand1) == 100, f"The number of frames is {len(rand1)}"
        assert len(rand1[0]) == 4, f"The size of the frame is {len(rand1[0])}"

    def test_random_spearmanrho1(self, test_client: GeneExpressionDatabaseClient):
        """Generate random expression results to be used in rho calculation."""
        metas: list[Metadata] = test_client.get_meta("maxilla")
        ingest_id: str = metas[0].ingestid

        gen: Generator = numpy.random.default_rng()
        gscores: list[float] = list(gen.random(10))
        rands: list[float] = test_client.random_spearmanrho(
            ingest_id=ingest_id, scores=gscores, r_size=100
        )
        assert len(rands) == 100, f"The number of randoms is {len(rands)}"

    def test_random_results_time(self, test_client: GeneExpressionDatabaseClient):
        """Generate random expression results to be used in rho calculation."""
        metas: list[Metadata] = test_client.get_meta("maxilla")
        ingest_id: str = metas[0].ingestid

        # These only really make sense when cs_server=True for test_client
        self._time(lambda g, r: test_client.random(ingest_id, g, r), 10, 10)
        self._time(lambda g, r: test_client.random(ingest_id, g, r), 10, 100)
        self._time(lambda g, r: test_client.random(ingest_id, g, r), 10, 1000)
        self._time(lambda g, r: test_client.random(ingest_id, g, r), 100, 1000)
        self._time(lambda g, r: test_client.random(ingest_id, g, r), 1000, 1000)

    def _time(self, func, g, r) -> None:

        print(f"\nRunning {g}x{r} generation")
        b4 = time.time()
        func(g, r)
        print(f"\nRandom {g}x{r} generation time {time.time() - b4}s")

    def _connective_tissue_disorder(
        self, test_client: GeneExpressionDatabaseClient
    ) -> list[DataResult]:
        genes = test_client.read_scores("tests/unit/connective_tissue_disorder_log2fc_test.csv")
        drequest = DataRequest(
            geneIds=list(genes.keys()),
            strains=["*"],  # All strains if not searching on limited set.
            sourceType=SourceType.IMPUTED.name,
            tissue="maxilla",
        )

        # This is a larger search size. When connected to a real database
        # it takes about 1.5-2 minutes. This is acceptable performance we think.
        return test_client.search(drequest)

    def _connective_tissue_disorder_expressions(
        self, test_client: GeneExpressionDatabaseClient
    ) -> list[StrainResult]:
        genes = test_client.read_scores("tests/unit/connective_tissue_disorder_log2fc_test.csv")
        drequest = DataRequest(
            geneIds=list(genes.keys()),
            strains=["*"],  # All strains if not searching on limited set.
            sourceType=SourceType.IMPUTED.name,
            tissue="maxilla",
        )

        # This is a larger search size. When connected to a real database
        # it takes about 1.5-2 minutes. This is acceptable performance we think.
        return test_client.search_expression(drequest)
