import sys
import logging
from pathlib import Path

from click import command

import roadgraphtool.exec
import roadgraphtool.config as config_module


input_file = r"C:\Google Drive\AIC Experiment Data\RGT/andorra-latest.osm"
output_file = r"C:\Google Drive\AIC Experiment Data\RGT/andorra-latest-filtered.osm"


args = sys.argv

if len(args) < 2:
    logging.error("You have to provide a path to the config file as an argument.")
    exit(-1)

config = config_module.parse_config_file(Path(args[1]))
config.log_level = 'DEBUG'
config_module.set_logging(config)

command = [
    'osmium',
    'tags-filter',
    input_file,
    'nwr/highway=motorway,motorway_link,trunk,trunk_link,primary,primary_link,secondary,secondary_link,tertiary,tertiary_link,unclassified,unclassified_link,residential,residential_link,living_street,service',
    '-o', output_file
]

roadgraphtool.exec.call_executable(command, output_type=roadgraphtool.exec.ReturnContent.STDOUT)
