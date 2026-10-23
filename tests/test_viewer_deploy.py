import ftplib
import types
from pathlib import Path

import pytest

from roadgraphtool import viewer_deploy


@pytest.fixture
def config(tmp_path):
    viewer_dir = tmp_path / 'viewer'
    viewer_dir.mkdir()
    for name in ['index.html', 'build.json', 'viewer.js', 'graph.bin']:
        (viewer_dir / name).write_text(name)
    return types.SimpleNamespace(
        viewer=types.SimpleNamespace(dir=viewer_dir),
        viewer_deploy=types.SimpleNamespace(
            activated=True, host='ftp.example.com', port=2121, tls=False, username='user', password='secret',
            remote_dir=Path('/www/map'),
        ),
    )


@pytest.fixture
def ftp(mocker):
    ftp = mocker.MagicMock(spec=ftplib.FTP)
    ftp.__enter__.return_value = ftp
    ftp.mkd.side_effect = ftplib.error_perm('550 exists')
    ftp.delete.side_effect = ftplib.error_perm('550 not found')
    mocker.patch('ftplib.FTP', return_value=ftp)
    return ftp


def test_deploy_viewer(config, ftp):
    viewer_deploy.deploy_viewer(config)

    ftp.connect.assert_called_once_with('ftp.example.com', 2121)
    ftp.login.assert_called_once_with('user', 'secret')
    assert [call.args[0] for call in ftp.mkd.call_args_list] == ['/', '/www', '/www/map']

    stored = [call.args[0] for call in ftp.storbinary.call_args_list]
    assert stored == [
        'STOR /www/map/graph.bin.part',
        'STOR /www/map/viewer.js.part',
        'STOR /www/map/build.json.part',
        'STOR /www/map/index.html.part',
    ]
    renamed = [call.args for call in ftp.rename.call_args_list]
    assert renamed == [
        ('/www/map/graph.bin.part', '/www/map/graph.bin'),
        ('/www/map/viewer.js.part', '/www/map/viewer.js'),
        ('/www/map/build.json.part', '/www/map/build.json'),
        ('/www/map/index.html.part', '/www/map/index.html'),
    ]
