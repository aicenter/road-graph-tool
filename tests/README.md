# Testing of processing and importing OSM file

## Dependencies
To test the functionality of the scripts, ensure you have the following installed:
- [pytest](https://docs.pytest.org/en/stable/)
- [pytest-mock](https://pypi.org/project/pytest-mock/)

## Tested scripts:
The following scripts are included in the tests:
- [filter_osm.py](../scripts/filter_osm.py)
- [process_osm.py](../roadgraphtool/process_osm.py)
- [schema.py](../roadgraphtool/schema.py)
- [map.py](../roadgraphtool/map.py)
- [distance_matrix_generator.py](../roadgraphtool/distance_matrix_generator.py)

Additionally, the [conftest.py](conftest.py) file is included to manage fixtures and shared configurations for the tests.

## Running the tests

Test scripts and their associated data are saved in this directory. Execute all the tests in terminal with:
```bash
pytest python/tests/
```

## Database connection

The `test_process_osm.py` script connects to database using credentials specified in `config.ini` file, so make sure to check that the connection details are correct.
Some databases require a password, so `pgpass.conf` file is automatically set up in root folder of the project when the `CREDENTIALS` is imported from [credentials_config.py](../roadgraphtool/credentials_config.py).