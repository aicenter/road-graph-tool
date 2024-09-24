import os
from sshtunnel import SSHTunnelForwarder

from roadgraphtool.credentials_config import CREDENTIALS as config

class SSHTunnelError(Exception):
    pass

def setup_ssh_tunnel(ssh_tunnel_port: int = 1111) -> SSHTunnelForwarder:
    """Establish an SSH tunnel to the remote server and return SSH tunnel forwarder.
    """
    try:
        if not os.path.exists(config.private_key_path):
            raise FileNotFoundError(f"Private key not found at {config.private_key_path}")

        tunnel = SSHTunnelForwarder(
            config.server,
            ssh_username=config.server_username,
            ssh_pkey=config.private_key_path,
            local_bind_address=(config.host, ssh_tunnel_port),
            remote_bind_address=(config.host, config.db_server_port)
        )
        tunnel.start()
        print(f"SSH tunnel established.")
        return tunnel
    except Exception as e:
        print(e)
        return None

def cancel_ssh_tunnel(tunnel: SSHTunnelForwarder):
    """Cancels the established SSH tunnel."""
    if tunnel is not None:
        tunnel.stop()
        print("SSH tunnel closed.")
    else:
        print("No SSH tunnel to close.")