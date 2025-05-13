# conftest.py (or your central test setup file)
import logging
import pytest

def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    logging.basicConfig(
        filename='test_run.log',
        filemode='w',  # Overwrite log file on each run
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info("Test session started.")

def pytest_sessionfinish(session, exitstatus):
    """
    Called after whole test run finished, right before
    returning the exit status to the system.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Test session finished. Exit status: {exitstatus}")
    if exitstatus == 0:
        logger.info("All tests passed.")
    else:
        logger.error(f"Some tests failed. Exit status: {exitstatus}")
        
        
def pytest_runtest_setup(item):
    """
    Called before each test item is run.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting test: {item.name}")