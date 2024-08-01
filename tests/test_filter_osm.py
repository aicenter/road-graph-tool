import os
import pathlib
import pytest
from python.scripts.filter_osm import check_strategy, extract_id

# TODO: automated pytest

def test_check_strategy():
    assert check_strategy("simple") == True
    assert check_strategy("complete_ways") == True
    assert check_strategy("smart") == True
    assert check_strategy("invalid_strategy") == False

def test_extract_id_remove_file(mocker):
    relation_id = 5986438
    input_file = "tests/data/park-sorted.osm"
    # test that tmp_file is not in folder
    parent_dir = pathlib.Path(__file__).parent.parent.parent
    tmp_file = str(parent_dir) + "/road-graph-tool/resources/to_extract.osm"
    mock_remove = mocker.patch("os.remove")
    mocker.patch("os.path.isfile", return_value=False)
    extract_id(relation_id, input_file)
    mock_remove.assert_called_once_with(tmp_file)
    assert not os.path.isfile(tmp_file)
    
# TODO: test_extract_id
def test_extract_id_remove_file(mocker):
    # test that tmp_file containing relation is same as created python/scripts/id_extract.osm.pbf
    # correctly filters out data from og_file based od id
    pass

# TODO: test_extract_bbox_osm2pgsql
# TODO: test_extract_bbox_osmium
# TODO: test_tags_filter