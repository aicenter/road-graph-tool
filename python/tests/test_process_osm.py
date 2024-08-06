import os
import pathlib
import pytest
import requests
import xml.etree.ElementTree as ET
import tempfile
import json

@pytest.fixture
def mock_subprocess_run(mocker):
    return mocker.patch("subprocess.run")

@pytest.fixture
def mock_os_path_isfile(mocker):
    return mocker.patch("os.path.isfile")