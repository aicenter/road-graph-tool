import pytest
import logging

from roadgraphtool.exec import call_executable, ReturnContent

@pytest.fixture
def set_debug_logging():
    logging.getLogger().setLevel(logging.DEBUG)
    yield
    logging.getLogger().setLevel(logging.WARNING)



def test_simple_return_bool():
    result = call_executable(["python", "--version"], output_type=ReturnContent.BOOL)
    assert result == True

def test_simple_return_stdout():
    result = call_executable(["python", "--version"], output_type=ReturnContent.STDOUT)
    assert result.startswith("Python")

def test_simple_return_bool_debug(capsys, set_debug_logging):
    result = call_executable(["python", "--version"], output_type=ReturnContent.BOOL)
    assert result == True
    captured = capsys.readouterr()
    assert "Python" in captured.out

def test_command_not_found_return_bool():
    result = call_executable(["nonexistent_command"], output_type=ReturnContent.BOOL)
    assert result == False

def test_command_not_found_return_stdout():
    with pytest.raises(OSError):
        call_executable(["nonexistent_command"], output_type=ReturnContent.STDOUT)

def test_command_result_not_zero_return_bool():
    result = call_executable(["python", "--non_existent_argument"], output_type=ReturnContent.BOOL)
    assert result == False

def test_command_result_not_zero_return_stdout():
    with pytest.raises(Exception):
        call_executable(["python", "--non_existent_argument"], output_type=ReturnContent.STDOUT)
