import ftplib
import logging
from pathlib import Path, PurePosixPath

from roadgraphtool.overpass_client import _read_nested

# uploaded last and in this order, so that the page never refers to data files that are not uploaded yet
LAST_FILES = ("build.json", "index.html")


def _ensure_remote_dir(ftp: ftplib.FTP, remote_dir: PurePosixPath):
    for directory in reversed([remote_dir, *remote_dir.parents]):
        try:
            ftp.mkd(str(directory))
        except ftplib.error_perm:
            # already exists
            pass


def _upload_file(ftp: ftplib.FTP, local_path: Path, remote_dir: PurePosixPath):
    """Uploads the file under a temporary name first, so that a half-written file is never served."""
    remote_path = str(remote_dir / local_path.name)
    temporary_path = f"{remote_path}.part"
    logging.info("Uploading %s (%.1f MB)", local_path.name, local_path.stat().st_size / 1_000_000)
    with open(local_path, "rb") as file:
        ftp.storbinary(f"STOR {temporary_path}", file)
    try:
        ftp.delete(remote_path)
    except ftplib.error_perm:
        # first upload
        pass
    ftp.rename(temporary_path, remote_path)


def deploy_viewer(config):
    """
    Uploads the viewer built by ``roadgraphtool.viewer.build_viewer`` (``viewer.dir``) to the FTP server configured in
    the ``viewer_deploy`` section.
    """
    section = config.viewer_deploy
    viewer_dir = Path(config.viewer.dir)
    # the config parser turns absolute paths into local paths, so on Windows, the separators have to be converted back
    remote_dir = PurePosixPath(Path(section.remote_dir).as_posix())
    port = _read_nested(config, "viewer_deploy.port", 21)

    files = sorted(path for path in viewer_dir.iterdir() if path.is_file())
    files.sort(key=lambda path: LAST_FILES.index(path.name) if path.name in LAST_FILES else -1)

    ftp = ftplib.FTP_TLS() if _read_nested(config, "viewer_deploy.tls", True) else ftplib.FTP()
    logging.info("Deploying the viewer to %s:%d%s", section.host, port, remote_dir)
    with ftp:
        ftp.connect(section.host, port)
        ftp.login(section.username, section.password)
        if isinstance(ftp, ftplib.FTP_TLS):
            ftp.prot_p()
        _ensure_remote_dir(ftp, remote_dir)
        for path in files:
            _upload_file(ftp, path, remote_dir)
    logging.info("Viewer deployed")
