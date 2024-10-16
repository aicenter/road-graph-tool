import logging
import logging.config
from pathlib import Path
import yaml

DEFAULT_LOG_YAML = Path(__file__).parent.parent.parent / "logging_config.yaml"

def setup_logger(logger_name: str) -> logging.Logger:
    with open(DEFAULT_LOG_YAML, 'r') as file:
        config = yaml.safe_load(file)
        logging.config.dictConfig(config)
    
    logger = logging.getLogger(logger_name)

    for handler in logger.handlers:
        print(type(handler))
        if isinstance(handler, logging.StreamHandler):
            handler.setFormatter(ColorFormatter(handler.formatter._fmt, handler.formatter.datefmt))
        elif isinstance(handler, logging.FileHandler):
            handler.setFormatter(logging.Formatter(handler.formatter._fmt, handler.formatter.datefmt))
    
    return logger

class ColorFormatter(logging.Formatter):
    COLORS = {
        'ERROR': '\033[1;31m',  # Bold red
        'RESET': '\033[0m',  # Reset color
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.msg = f"{color}{record.msg}{self.COLORS['RESET']}"
        return super().format(record)