import sys
import logging
import platform
import subprocess
from typing import List, Optional, Tuple, Union
from enum import Enum

signal_status_codes = {
    1: {'signal': 'SIGHUP', 'action': '3',
        'desc': 'Hangup detected on controlling terminal or death of controlling process'},
    2: {'signal': 'SIGINT', 'action': '3', 'desc': 'Interrupt from keyboard'},
    3: {'signal': 'SIGQUIT', 'action': '3', 'desc': 'Quit from keyboard'},
    4: {'signal': 'SIGILL', 'action': '3', 'desc': 'Illegal Instruction'},
    6: {'signal': 'SIGABRT', 'action': '3', 'desc': 'Abort signal from abort(3)'},
    8: {'signal': 'SIGFPE', 'action': '3', 'desc': 'Floating point exception'},
    9: {'signal': 'SIGKILL', 'action': '3', 'desc': 'Kill signal'},
    11: {'signal': 'SIGSEGV', 'action': '3', 'desc': 'Invalid memory reference'},
    13: {'signal': 'SIGPIPE', 'action': '3', 'desc': 'Broken pipe: write to pipe with no readers'},
    14: {'signal': 'SIGALRM', 'action': '3', 'desc': 'Timer signal from alarm(2)'},
    15: {'signal': 'SIGTERM', 'action': '3', 'desc': 'Termination signal'}
}


class ReturnContent(Enum):
    STDOUT = 1
    BOOL = 2
    EXIT_CODE = 3


def decode_exit_status_code(code: int) -> Optional[Tuple[int, str, str, str]]:
    os_name = platform.system()
    if os_name == 'Linux':
        code = -code
        if code in signal_status_codes:
            data = signal_status_codes[code]
            return code, data['signal'], data['action'], data['desc']

    return None


def call_executable(command: List[str], timeout: Optional[int] = None, output_type: ReturnContent = ReturnContent.BOOL) -> \
Union[str, bool, int]:
    logging.info("Calling external command: %s", " ".join(command))

    args = {
        'args': command,
        # 'stdout': sys.stdout,
        # 'stderr': subprocess.STDOUT,
    }

    if timeout:
        args['timeout'] = timeout
    try:
        result = subprocess.run(**args, check=True, capture_output=True, universal_newlines=True)

        if output_type == ReturnContent.STDOUT:
            return result.stdout
        elif output_type == ReturnContent.BOOL:
            return True
        else:
            return result.returncode

    except FileNotFoundError:
        logging.error("Executable %s not found. Check if the full path to the executable is in "
                      "the system PATH environment variable.", command[0])
        if output_type == ReturnContent.BOOL:
            return False
        raise

    except subprocess.CalledProcessError as command_error:
        logging.error("Executable run failed for command: %s", command_error.cmd)

        # stderr output
        if command_error.stderr:
            logging.error("Executable stderr output START\n%s", command_error.stderr)
            logging.error("Executable stderr output END.")

        # exit code
        decoded = decode_exit_status_code(command_error.returncode)
        if decoded:
            logging.info('Exit status code: %d: %s (%s)', decoded[0], decoded[1], decoded[3])
        else:
            logging.info("Exist status code: %d", command_error.returncode)

        # stdout output
        if command_error.output:
            logging.error("Executable output START\n%s", command_error.output)
            logging.error("Executable output END.")

        # exception handling
        if output_type == ReturnContent.BOOL:
            return False
        raise
    except subprocess.TimeoutExpired:
        logging.warning("Timeout expired (%d)", timeout)
        if output_type == ReturnContent.BOOL:
            return False
        raise
