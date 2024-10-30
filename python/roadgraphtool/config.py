import yaml
import types
from pathlib import Path


def dict2obj(data):
    """Convert dictionary to object. Taken from https://stackoverflow.com/questions/66208077"""
    if type(data) is list:
        return list(map(dict2obj, data))
    elif type(data) is dict:
        sns = types.SimpleNamespace()
        for key, value in data.items():
            setattr(sns, key, dict2obj(value))
        return sns
    else:
        return data


def parse_config_file(config_file: Path):
    with open(config_file, 'r',encoding="UTF-8") as file:
        config_dict = yaml.safe_load(file)
        config_dict['config_dir'] = config_file.parent
        config_object = dict2obj(config_dict)

    return config_object

def get_path_from_config(config, path_string):
    path = Path(path_string)
    if not path.is_absolute():
        path = config.config_dir / path
    return path