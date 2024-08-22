import os
import pytest
import logging
import geopandas as gpd

from roadgraphtool.distance_matrix_generator import generate_dm, _set_config_defaults


# set_config_defaults
def test_set_config_defaults_simple():
    config = {}
    defaults = {'key1': 'value1', 'key2': 'value2'}
    _set_config_defaults(config, defaults)
    assert config == {'key1': 'value1', 'key2': 'value2'}


def test_set_config_defaults_with_existing_keys():
    config = {'key1': 'existing_value1'}
    defaults = {'key1': 'value1', 'key2': 'value2'}
    _set_config_defaults(config, defaults)
    assert config == {'key1': 'existing_value1', 'key2': 'value2'}


def test_set_config_defaults_nested():
    config = {'outer_key': {'inner_key1': 'existing_inner_value1'}}
    defaults = {'outer_key': {'inner_key1': 'inner_value1', 'inner_key2': 'inner_value2'}}
    _set_config_defaults(config, defaults)
    assert config == {'outer_key': {'inner_key1': 'existing_inner_value1', 'inner_key2': 'inner_value2'}}


def test_set_config_defaults_with_empty_defaults():
    config = {'key1': 'value1'}
    defaults = {}
    _set_config_defaults(config, defaults)
    assert config == {'key1': 'value1'}


def test_set_config_defaults_with_empty_config():
    config = {}
    defaults = {'key1': 'value1'}
    _set_config_defaults(config, defaults)
    assert config == {'key1': 'value1'}


def test_set_config_defaults_complex():
    config = {'outer_key': {'inner_key1': 'existing_inner_value1'}, 'key2': 'existing_value2'}
    defaults = {'outer_key': {'inner_key1': 'inner_value1', 'inner_key2': 'inner_value2'}, 'key2': 'value2',
                'key3': 'value3'}
    _set_config_defaults(config, defaults)
    assert config == {'outer_key': {'inner_key1': 'existing_inner_value1', 'inner_key2': 'inner_value2'},
                      'key2': 'existing_value2', 'key3': 'value3'}


# generate_dm
@pytest.fixture
def nodes():
    return gpd.GeoDataFrame({
        'db_id': [1, 2],
        'x': [0.0, 1.0],
        'y': [0.0, 0.0],
    })


@pytest.fixture
def edges():
    return gpd.GeoDataFrame({
        'u': [1.0, -1.0],
        'v': [0.0, 0.0],
        'db_id_from': [1, 2],
        'db_id_to': [2, 1],
        'length': [1.0, 1.0]
    })


@pytest.fixture
def config():
    return {
        'area_dir': './',
        'map': {
            'path': './'
        },
    }


def test_simple_area_dir(config, nodes, edges):
    generate_dm(config, nodes, edges)

    assert os.path.exists('./dm.csv')


def test_simple_dm_filepath(nodes, edges):
    config = {
        'dm_filepath': './dm1',
        'area_dir': './',
        'map': {
            'path': './'
        },
    }

    generate_dm(config, nodes, edges)

    assert os.path.exists('./dm1.csv')


def test_generate_dm_skip_generation(caplog, config, nodes, edges):
    generate_dm(config, nodes, edges)

    with caplog.at_level(logging.INFO):
        generate_dm(config, nodes, edges)

    assert 'Skipping DM generation, the file is already generated.' in caplog.text


def test_generate_dm_travel_time(config, nodes, edges):

    if os.path.exists('./dm.csv'):
        os.remove('./dm.csv')

    generate_dm(config, nodes, edges)
    assert 'travel_time' in edges.columns
    assert edges['travel_time'].at[0] == 0
    assert edges['travel_time'].at[1] == 0
