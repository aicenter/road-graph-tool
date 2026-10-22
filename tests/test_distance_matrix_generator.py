import pytest
import logging
import pandas as pd
import geopandas as gpd
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from roadgraphtool.distance_matrix_generator import (
    generate_dm,
    _set_config_defaults,
    _normalize_dm_output_format,
    _get_dm_output_format,
    _get_default_speed_mps,
)


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


def test_normalize_dm_output_format():
    assert _normalize_dm_output_format("CSV") == "csv"
    assert _normalize_dm_output_format("hdf") == "hdf"


def test_normalize_dm_output_format_invalid():
    with pytest.raises(ValueError, match="Unsupported dm output format"):
        _normalize_dm_output_format("parquet")


def test_get_dm_output_format_default():
    assert _get_dm_output_format({}) == "csv"


def test_get_dm_output_format_from_dm_generator():
    config = {"dm_generator": {"output_format": "hdf"}}
    assert _get_dm_output_format(config) == "hdf"


def test_default_speed_without_config_is_14_mps():
    assert _get_default_speed_mps({}) == 14


def test_default_speed_from_dm_generator():
    config = SimpleNamespace(dm_generator=SimpleNamespace(default_speed_kmh=5))
    assert _get_default_speed_mps(config) == pytest.approx(5 / 3.6)


def test_default_speed_must_be_positive():
    with pytest.raises(ValueError, match="must be positive"):
        _get_default_speed_mps({"dm_generator": {"default_speed_kmh": 0}})


@pytest.fixture
def mock_dm_exec():
    calls = []

    def fake_call(command):
        calls.append(command)
        output_format = command[command.index("--output-format") + 1]
        out_path = Path(command[command.index("-o") + 1])
        if output_format == "csv":
            out_file = out_path if out_path.suffix == ".csv" else Path(str(out_path) + ".csv")
            out_file.write_text("0,10,4294967295\n10,0,4294967295\n14,10,0\n")
        else:
            out_file = out_path if out_path.suffix == ".h5" else out_path.with_suffix(".h5")
            out_file.write_bytes(b"hdf5")
        return True

    with patch(
        "roadgraphtool.distance_matrix_generator.roadgraphtool.exec.call_executable",
        side_effect=fake_call,
    ):
        yield calls


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
        'export': {'dir': tmp_path},
        'map': {
            'path': tmp_path
        }
    }


def test_simple_area_dir(config, sample_nodes, sample_edges, tmp_path, mock_dm_exec):
    generate_dm(config, sample_nodes, sample_edges)

    assert (tmp_path / 'dm.csv').exists()


def test_simple_dm_filepath(sample_nodes, sample_edges, tmp_path, mock_dm_exec):
    config = {
        'dm_filepath': tmp_path / 'dm1',
        'export': {'dir': tmp_path},
        'map': {
            'path': tmp_path
        },
    }

    generate_dm(config, sample_nodes, sample_edges)

    assert (tmp_path / 'dm1.csv').exists()


def test_generate_dm_hdf_format(sample_nodes, sample_edges, tmp_path, mock_dm_exec):
    config = {
        'export': {'dir': tmp_path},
        'dm_generator': {'output_format': 'hdf'},
        'map': {'path': tmp_path},
    }

    generate_dm(config, sample_nodes, sample_edges)

    command = mock_dm_exec[0]
    assert command[command.index("--output-format") + 1] == "hdf"
    assert (tmp_path / 'dm.h5').exists()


def test_generate_dm_skip_generation(caplog, config, sample_nodes, sample_edges, mock_dm_exec):
    generate_dm(config, sample_nodes, sample_edges)

    with caplog.at_level(logging.INFO):
        generate_dm(config, sample_nodes, sample_edges)

    assert 'Skipping DM generation, the file is already generated.' in caplog.text


def test_generate_dm_travel_time(config, sample_nodes, sample_edges, mock_dm_exec):
    generate_dm(config, sample_nodes, sample_edges)
    assert 'travel_time' in sample_edges.columns
    assert sample_edges['travel_time'].at[0] == 10
    assert sample_edges['travel_time'].at[1] == 10


def test_generate_dm_travel_time_default_speed(config, sample_nodes, sample_edges, mock_dm_exec):
    edges = sample_edges.drop(columns=['speed'])

    generate_dm(config, sample_nodes, edges)

    # 100 m and 140 m at 14 m/s
    assert edges['travel_time'].tolist() == [7, 7, 10, 7]


def test_generate_dm_travel_time_configured_default_speed(config, sample_nodes, sample_edges, mock_dm_exec):
    config['dm_generator'] = {'default_speed_kmh': 5}
    edges = sample_edges.drop(columns=['speed'])

    generate_dm(config, sample_nodes, edges)

    # 100 m and 140 m at 5 km/h
    assert edges['travel_time'].tolist() == [72, 72, 101, 72]


def test_generate_dm(config, sample_nodes, sample_edges, tmp_path, mock_dm_exec):

    generate_dm(config, sample_nodes, sample_edges)

    df = pd.read_csv(tmp_path / 'dm.csv', header=None)
    expected_df = pd.DataFrame([
        [0, 10, 4294967295],
        [10, 0, 4294967295],
        [14, 10, 0],
    ])
    pd.testing.assert_frame_equal(df, expected_df)


def test_generate_dm_namespace_config(sample_nodes, sample_edges, tmp_path, mock_dm_exec):
    config = SimpleNamespace(
        export=SimpleNamespace(dir=tmp_path),
        dm_generator=SimpleNamespace(output_format="csv"),
    )
    generate_dm(config, sample_nodes, sample_edges)
    assert (tmp_path / "dm.csv").exists()
