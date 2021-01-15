import sys
import click
import logging
import unittest
from xmlrunner import XMLTestRunner

from flask.cli import AppGroup

manage = AppGroup('manage')

TEST_DIR = 'tests'

@click.command('test')
@click.option('-x', '--xml', 'xml', is_flag=True, help='Set this flag to output XML test results for Bamboo')
def run_tests(xml):
    """
    Run tests for the application.
    """
    logging.basicConfig(stream=sys.stderr)
    result = _run_tests_xml(TEST_DIR) if xml else _run_tests_nornal(TEST_DIR)
    return 0 if result.wasSuccessful() else 1

def _run_tests_nornal(test_dir):
    """ Runs tests and outputs results to cli"""
    tests = unittest.TestLoader().discover(test_dir, pattern='test*.py')
    return unittest.TextTestRunner(verbosity=2).run(tests)


def _run_tests_xml(test_dir):
    """ Runs the unit tests specifically for bamboo CI/CD """
    tests = unittest.TestLoader().discover(test_dir, pattern='test*.py')
    return XMLTestRunner(output='test-reports').run(tests)

