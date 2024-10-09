import logging
import logging.config
from pathlib import Path
import yaml

DEFAULT_LOG_YAML = Path(__file__).parent.parent.parent / "logging_config.yaml"

def setup_logger(logger_name: str) -> logging.Logger:
    with open(DEFAULT_LOG_YAML, 'r') as file:
        config = yaml.safe_load(file)
        logging.config.dictConfig(config)
    
    return logging.getLogger(logger_name)