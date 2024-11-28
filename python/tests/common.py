import importlib.resources

from pathlib import Path
from importlib.resources import files

from roadgraphtool.config import parse_config_file

TESTS_DIR = Path(__file__).parent.parent.parent / "python/tests/data"

test_resources_path = "python.tests.data"

test_config_file = files(test_resources_path).joinpath("config.yaml")

config = parse_config_file(test_config_file)