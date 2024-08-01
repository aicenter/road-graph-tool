import pytest
from python.scripts.filter_osm import check_strategy

def test_check_strategy():
    assert check_strategy("simple") == True
    assert check_strategy("complete_ways") == True
    assert check_strategy("smart") == True
    assert check_strategy("invalid_strategy") == False

if __name__ == '__main__':
    pytest.main()
