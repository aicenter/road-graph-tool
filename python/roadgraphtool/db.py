
from roadgraphtool.credentials_config import CREDENTIALS


def get_sql_alchemy_engine_str(config: CREDENTIALS, server_port):
    sql_alchemy_engine_str = 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'.format(
        user=config.username,
        password=config.db_password,
        host=config.db_host,
        port=server_port,
        dbname=config.db_name)

    return sql_alchemy_engine_str