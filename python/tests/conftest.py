import pytest

from importlib.resources import files



test_resources_path = "tests.resources"




@pytest.fixture
def mock_subprocess_run(mocker):
    return mocker.patch("subprocess.run")

@pytest.fixture
def mock_os_path_isfile(mocker):
    return mocker.patch("os.path.isfile")

@pytest.fixture
def mock_remove(mocker):
    return mocker.patch("os.remove")

