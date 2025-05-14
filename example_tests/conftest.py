import logging
import pytest
import os

# Determine project root (assuming conftest.py is in 'example_tests')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Define the reports directory path
REPORTS_DIR = os.path.join(PROJECT_ROOT, 'reports')
# Define the full path for the log file
LOG_FILE_PATH = os.path.join(REPORTS_DIR, 'test_run.log')

# Ensure the reports directory exists
if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR)

def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) # Set root logger level

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
    )

    # File handler - with UTF-8 encoding
    file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO) # Set level for this handler
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO) # Set level for this handler
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logger = logging.getLogger(__name__)
    logger.info(f"Test session started. Logging to: {LOG_FILE_PATH}")

def pytest_sessionfinish(session, exitstatus):
    """
    Called after the whole test run finishes.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Test session finished. Exit status: {exitstatus}")
    if exitstatus == 0:
        logger.info("All tests passed.")
    else:
        logger.error("Some tests failed.")

def pytest_runtest_setup(item):
    """
    Called before each test item is run.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting test: {item.name}")

def pytest_runtest_logreport(report):
    """
    Called after each phase of a test item (setup/call/teardown).
    """
    if report.when == "call":
        logger = logging.getLogger(report.nodeid) # Use test's specific logger name
        if report.passed:
            logger.info(f"✅ Test passed: {report.nodeid.split('::')[-1]}")
        elif report.failed:
            # The actual error traceback will be logged by pytest's default mechanisms
            # or by specific error logging within the test/application code.
            # This log entry confirms the failure from pytest's perspective.
            logger.error(f"❌ Test failed: {report.nodeid.split('::')[-1]}")
            # You could optionally log report.longreprtext for more details here if needed
            # logger.error(f"Failure details: {report.longreprtext}")
        elif report.skipped:
            logger.warning(f"⚠️ Test skipped: {report.nodeid.split('::')[-1]} - Reason: {report.longrepr.splitlines()[-1]}")

@pytest.fixture
def test_logger(request):
    """
    Fixture to provide a logger named after the test function.
    This makes it easier to trace logs back to specific tests.
    """
    return logging.getLogger(request.node.name)

@pytest.fixture(autouse=True)
def setup_and_teardown_environment(): # Renamed for clarity
    """
    Autouse fixture to log setup and teardown phases for the test environment.
    """
    logger = logging.getLogger(__name__ + ".environment") # Specific logger for environment
    logger.info("Test environment setup starting.")
    # Setup code (if any)
    # logger.info("Test environment setup complete.")
    yield
    # Teardown code (if any)
    logger.info("Tearing down test environment.")
    # Close any open resources, if necessary
    # logger.info("Test environment torn down.")