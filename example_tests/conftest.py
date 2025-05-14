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
os.makedirs(REPORTS_DIR, exist_ok=True)

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
        # Use the test's specific logger name, replacing '::' for valid logger hierarchy
        logger_name = report.nodeid.replace("::", ".")
        logger = logging.getLogger(logger_name)
        test_short_name = report.nodeid.split('::')[-1]

        if report.passed:
            logger.info(f"✅ Test passed: {test_short_name}")
        elif report.failed:
            # The actual error traceback will be logged by pytest's default mechanisms
            # or by specific error logging within the test/application code.
            # This log entry confirms the failure from pytest's perspective.
            logger.error(f"❌ Test failed: {test_short_name}")
            # You could optionally log report.longreprtext for more details here if needed
            # logger.error(f"Failure details: {report.longreprtext}")
        elif report.skipped:
            reason = "No explicit reason" # Default
            if report.outcome == 'xfailed' and hasattr(report, 'wasxfail') and report.wasxfail:
                reason = f"XFAIL (expected failure): {report.wasxfail}"
            elif report.longreprtext:
                text = report.longreprtext.strip()
                if "Skipped: " in text: # For pytest.skip() or @pytest.mark.skip()
                    reason = text.split("Skipped: ", 1)[-1]
                elif text: # Fallback for other skip messages if any
                    reason = text.splitlines()[-1] if text.splitlines() else text
            logger.warning(f"⚠️ Test skipped: {test_short_name} - Reason: {reason}")

@pytest.fixture
def test_logger(request):
    """
    Fixture to provide a logger named after the test function.
    This makes it easier to trace logs back to specific tests.
    """
    # Using nodeid and replacing '::' makes it more unique and logger-name friendly
    return logging.getLogger(request.node.nodeid.replace("::", "."))

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