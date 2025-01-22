from contextlib import AbstractContextManager
from importlib.abc import Traversable
from typing import Union

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


def expand_relative_paths(config_object: types.SimpleNamespace, root_dir: Path):
    for key, value in vars(config_object).items():
        if isinstance(value, str):
            if value.startswith('./'):
                setattr(config_object, key, root_dir / value[2:])
        # for objects, call recursively
        elif isinstance(value, types.SimpleNamespace):
            expand_relative_paths(value, root_dir)

def merge_dicts(dict_a, dict_b):
    merged = dict_a.copy()  # Start with a copy of the first dictionary

    for key, value in dict_b.items():
        if key in merged:
            # If the key exists in both dictionaries and both values are dictionaries, merge them recursively
            if isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = merge_dicts(merged[key], value)
            else:
                # If there's a conflict at this level, you could decide to keep dict_a's value or replace it
                merged[key] = value
        else:
            # If the key is only in dict_b, add it to the merged dictionary
            merged[key] = value

    return merged


def parse_config_file(config_file: Union[Path, Traversable]):
    with open(config_file, 'r',encoding="UTF-8") as file:
        config_dict = yaml.safe_load(file)

        # merge in the secrets file
        secrets_file_path = Path(config_dict['password_config_file'])
        # expand path if relative
        if not secrets_file_path.is_absolute():
            secrets_file_path = config_file.parent / secrets_file_path
        with open(secrets_file_path, 'r',encoding="UTF-8") as secrets_file:
            secrets_dict = yaml.safe_load(secrets_file)
            config_dict = merge_dicts(config_dict, secrets_dict)

        config_object = dict2obj(config_dict)
        expand_relative_paths(config_object, config_file.parent)
        return config_object

def get_path_from_config(config, path_string) -> Path:
    path = Path(path_string)
    if not path.is_absolute():
        path = config.config_dir / path
    return path