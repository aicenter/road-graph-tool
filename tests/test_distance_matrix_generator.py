import pytest
import logging
import pandas as pd
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
def sample_nodes():
    return gpd.GeoDataFrame({
        'db_id': [10, 20, 30],
    })


@pytest.fixture
def sample_edges():
    return gpd.GeoDataFrame({
        'u': [0, 1, 0, 1],
        'v': [1, 2, 2, 0],
        'length': [100, 100, 140, 100],
        'speed': [36, 36, 36, 36]
    })


@pytest.fixture
def config(tmp_path):
    return {
        'area_dir': tmp_path,
        'map': {
            'path': tmp_path
        }
    }


def test_simple_area_dir(config, sample_nodes, sample_edges, tmp_path):
    generate_dm(config, sample_nodes, sample_edges)

    assert (tmp_path / 'dm.csv').exists()


def test_simple_dm_filepath(sample_nodes, sample_edges, tmp_path):
    config = {
        'dm_filepath': tmp_path / 'dm1',
        'area_dir': tmp_path,
        'map': {
            'path': tmp_path
        },
    }

    generate_dm(config, sample_nodes, sample_edges)

    assert (tmp_path / 'dm1.csv').exists()


def test_generate_dm_skip_generation(caplog, config, sample_nodes, sample_edges):
    generate_dm(config, sample_nodes, sample_edges)

    with caplog.at_level(logging.INFO):
        generate_dm(config, sample_nodes, sample_edges)

    assert 'Skipping DM generation, the file is already generated.' in caplog.text


def test_generate_dm_travel_time(config, sample_nodes, sample_edges):
    generate_dm(config, sample_nodes, sample_edges)
    assert 'travel_time' in sample_edges.columns
    assert sample_edges['travel_time'].at[0] == 10
    assert sample_edges['travel_time'].at[1] == 10


def test_generate_dm(config, sample_nodes, sample_edges, tmp_path):

    generate_dm(config, sample_nodes, sample_edges)

    df = pd.read_csv((tmp_path / 'dm.csv'))

    expected_df = pd.DataFrame({
        '0': [10, 4294967295],
        '10': [0, 4294967295],
        '14': [10, 0]})

    pd.testing.assert_frame_equal(df, expected_df)
