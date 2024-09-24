import os
from sshtunnel import SSHTunnelForwarder

from roadgraphtool.credentials_config import CREDENTIALS as config

def setup_ssh_tunnel(ssh_port: int = 22, remote_port: int = 5432) -> SSHTunnelForwarder:
    """Establish an SSH tunnel to the remote server and return SSH tunnel forwarder.

    Args:
    - ssh_port: SSH server port (usually 22).
    - remote_port: Remote port (default is 5432 for PostgreSQL).
    """
    try:
        if not os.path.exists(config.private_key_path):
            raise FileNotFoundError(f"Private key not found at {config.private_key_path}")

        tunnel = SSHTunnelForwarder(
            (config.server, ssh_port),
            ssh_username=config.server_username,
            ssh_pkey=config.private_key_path,
            local_bind_address=('127.0.0.1', config.db_server_port),
            remote_bind_address=(config.host, remote_port)
        )
        tunnel.start()
        print(f"SSH tunnel established.")
        return tunnel
    except Exception as e:
        print(f"Failed to establish SSH tunnel: {e}")
        return None

def cancel_ssh_tunnel(tunnel: SSHTunnelForwarder):
    """Cancels the established SSH tunnel."""
    if tunnel is not None:
        tunnel.stop()
        print("SSH tunnel closed.")
    else:
        print("No SSH tunnel to close.")