"""
Centralized Logging Configuration
Provides consistent logging setup across all modules
"""

import logging
from pathlib import Path

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

def setup_logger(name, log_file=None, level=logging.INFO):
    """
    Set up a logger with both file and console handlers
    
    Args:
        name: Logger name (usually __name__)
        log_file: Optional specific log file name
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File handler (detailed logs)
    if log_file is None:
        log_file = f"{name.replace('.', '_')}.log"
    
    file_handler = logging.FileHandler(LOGS_DIR / log_file)
    file_handler.setLevel(logging.DEBUG)  # File gets all messages
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler (less verbose)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Console shows INFO and above
    console_handler.setFormatter(simple_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def setup_error_logger():
    """
    Set up a dedicated logger for all errors across the application
    
    Returns:
        Error logger instance
    """
    error_logger = logging.getLogger('error_logger')
    error_logger.setLevel(logging.ERROR)
    
    # Avoid adding duplicate handlers
    if error_logger.handlers:
        return error_logger
    
    # Error log file with timestamp
    error_log_file = LOGS_DIR / 'errors.log'
    
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d]\n'
        'Exception: %(message)s\n'
        '%(exc_info)s\n',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(error_log_file)
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(error_formatter)
    
    error_logger.addHandler(file_handler)
    
    return error_logger


def log_exception(logger, message, exc_info=True):
    """
    Utility function to log exceptions with full traceback
    
    Args:
        logger: Logger instance
        message: Error message
        exc_info: Include exception traceback (default: True)
    """
    logger.error(message, exc_info=exc_info)
    
    # Also log to dedicated error logger
    error_logger = setup_error_logger()
    error_logger.error(f"{logger.name}: {message}", exc_info=exc_info)


# Module-level loggers for common components
browser_logger = setup_logger('browser_recorder', 'browser_recorder.log')
ui_logger = setup_logger('ui', 'ui.log')
executor_logger = setup_logger('executor', 'executor.log')
vlm_logger = setup_logger('vlm', 'vlm.log')
error_logger = setup_error_logger()


if __name__ == "__main__":
    # Test logging setup
    test_logger = setup_logger('test_module')
    test_logger.info("This is an info message")
    test_logger.warning("This is a warning message")
    test_logger.error("This is an error message")
    
    try:
        # Test exception logging
        raise ValueError("Test exception for logging demonstration")
    except Exception:
        log_exception(test_logger, "Test exception occurred")
    
    print(f"\nLog files created in: {LOGS_DIR}")
    print("Check the following files:")
    for log_file in LOGS_DIR.glob('*.log'):
        print(f"  - {log_file.name}")
