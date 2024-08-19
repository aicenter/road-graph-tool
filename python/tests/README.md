### Testing of processing and importing OSM file

Testing of the functionality of both scripts (`filter_osm.py`, `process_osm.py`) is done via `pytest` and `pytest-mock` module.
- Make sure to have it installed: `pip install -U pytest` and `pip install pytest-mock` (Ubuntu/MacOS)
Test scripts and data used by them are saved in `/python/tests/` directory. Run all the tests from top directory in command line with:
```bash
pytest python/tests/
```

Testing script `test_process_osm.py` uses connection to database specified in `config.ini` file, so make sure to check that the connection details are correct and that the database server is running.
If the server database requires password, you store it to your home directory in `.pgpass` (Ubuntu/MacOS, [Windows](https://www.postgresql.org/docs/current/libpq-pgpass.html)) file in following format:
`hostname:port:database:username:password`.