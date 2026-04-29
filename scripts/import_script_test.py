from pathlib import Path

from roadgraphtool.db import db

sql_file = Path(r"D:\Workspaces\AIC\road-graph-tool\SQL\tests/run_all_tests.sql")

db.execute_script(r"D:\Workspaces\AIC\road-graph-tool\SQL\test.sql")

db.execute_script(sql_file)