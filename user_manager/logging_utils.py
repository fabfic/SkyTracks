import logging
import sys

def setup_logging():
    """
    Configure the root logger for the application.

    - Sets the log level to INFO
    - Outputs logs to standard output (stdout)
    - Applies a uniform log format including timestamp, level, logger name,
      and message

    This function should be called once during application startup.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger.addHandler(handler)
