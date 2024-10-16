import logging
import logging.config
from pathlib import Path
import yaml

DEFAULT_LOG_YAML = Path(__file__).parent.parent.parent / "logging_config.yaml"

class ColorFormatter(logging.Formatter):
    COLORS = {
        'ERROR': '\033[1;31m',  # Bold red
        'RESET': '\033[0m',  # Reset color
    }

    def format(self, record):
        original_msg = record.msg
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.msg = f"{color}{record.msg}{self.COLORS['RESET']}"
        formatted = super().format(record)
        record.msg = original_msg
        return formatted
    
class CustomLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CustomLogger, cls).__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self) -> logging.Logger:
        with open(DEFAULT_LOG_YAML, 'r') as file:
            config = yaml.safe_load(file)
            logging.config.dictConfig(config)
        
        for logger_name in config['loggers']:
            logger = logging.getLogger(logger_name)

            # set formatting
            for handler in logger.handlers:
                # print(f"Handler: {type(handler)}")  # Print type of the handler
                if isinstance(handler, logging.FileHandler):
                    handler.setFormatter(logging.Formatter(handler.formatter._fmt, handler.formatter.datefmt))
                    # print("Using FileFormatter for file handler.")
                elif isinstance(handler, logging.StreamHandler):
                    handler.setFormatter(ColorFormatter(handler.formatter._fmt, handler.formatter.datefmt))
                    # print("Using ColorFormatter for stream handler.")
    
    def get_logger(self, logger_name: str) -> logging.Logger:
        return logging.getLogger(logger_name)
    
LOGGER = CustomLogger()