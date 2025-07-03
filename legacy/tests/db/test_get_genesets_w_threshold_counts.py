# File: tests/db/test_get_genesets_w_threshold_counts.py
"""
Unit tests for the `get_geneset_ids_with_threshold_counts` function.

This test file uses the `unittest` framework to validate the behavior of the function.
The database interactions are mocked using `unittest.mock` to isolate the function logic.

Mocking:
- The `PooledCursor` class is mocked to avoid actual database calls.
- The `tools` module is mocked to resolve the `ModuleNotFoundError`.

Usage:
Run this test file using the `unittest` framework:
    `python -m unittest tests/db/test_get_genesets_w_threshold_counts.py`
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from src.geneweaverdb import get_geneset_ids_with_threshold_counts

class TestGetGenesetIdsWithThresholdCounts(unittest.TestCase):
    def setUp(self):
        """
        Sets up the test environment by mocking the `PooledCursor` class and the `tools` module.
        """
        # Mock the PooledCursor
        self.patcher_cursor = patch('src.geneweaverdb.PooledCursor')
        self.mock_pooled_cursor = self.patcher_cursor.start()
        self.mock_cursor_instance = MagicMock()
        self.mock_pooled_cursor.return_value.__enter__.return_value = self.mock_cursor_instance

        # Mock the tools module and its attributes
        self.mock_tools = MagicMock()
        self.mock_tools.toolcommon = MagicMock()
        sys.modules['tools'] = self.mock_tools

    def tearDown(self):
        """
        Cleans up the test environment by stopping the mocks.
        """
        self.patcher_cursor.stop()
        sys.modules.pop('tools', None)

    def test_valid_geneset_ids(self):
        """
        Tests the function with a list of valid geneset IDs.
        Verifies that the returned counts match the mocked database response.
        """
        self.mock_cursor_instance.fetchall.return_value = [
            (1, 10),
            (2, 20),
            (3, -1)
        ]

        geneset_ids = [1, 2, 3]
        result = get_genesets_with_threshold_counts(geneset_ids)

        expected_result = [
            {"geneset_id": 1, "threshold_count": 10},
            {"geneset_id": 2, "threshold_count": 20},
            {"geneset_id": 3, "threshold_count": -1}
        ]
        self.assertEqual(result, expected_result)

    def test_empty_geneset_ids(self):
        """
        Tests the function with an empty list of geneset IDs.
        Ensures the function returns an empty list.
        """
        self.mock_cursor_instance.fetchall.return_value = []

        geneset_ids = []
        result = get_genesets_with_threshold_counts(geneset_ids)

        self.assertEqual(result, [])

    def test_invalid_geneset_ids(self):
        """
        Tests the function with geneset IDs that do not exist in the database.
        Verifies that the function returns an empty list.
        """
        self.mock_cursor_instance.fetchall.return_value = []

        geneset_ids = [9999]  # IDs that do not exist
        result = get_genesets_with_threshold_counts(geneset_ids)

        self.assertEqual(result, [])

    def test_threshold_type_edge_cases(self):
        """
        Tests the function with edge cases for threshold types.
        Validates the counts for different threshold types, including binary (-1) and range-based counts.
        """
        self.mock_cursor_instance.fetchall.return_value = [
            (1, 0),
            (2, -1),
            (3, 100)
        ]

        geneset_ids = [1, 2, 3]
        result = get_genesets_with_threshold_counts(geneset_ids)

        expected_result = [
            {"geneset_id": 1, "threshold_count": 0},
            {"geneset_id": 2, "threshold_count": -1},
            {"geneset_id": 3, "threshold_count": 100}
        ]
        self.assertEqual(result, expected_result)

if __name__ == '__main__':
    unittest.main()