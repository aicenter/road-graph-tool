import sys
import logging
import platform
import subprocess
import threading
from typing import List, Optional, Tuple, Union
from enum import Enum

_signal_status_codes = {
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


def _decode_exit_status_code(code: int) -> Optional[Tuple[int, str, str, str]]:
    os_name = platform.system()
    if os_name == 'Linux':
        code = -code
        if code in _signal_status_codes:
            data = _signal_status_codes[code]
            return code, data['signal'], data['action'], data['desc']

    return None


def _stream_output(stream, output_list, output_stream):
    """Read a stream line by line and store the output."""
    for line in iter(stream.readline, ''):
        output_list.append(line)  # Store the line in the output list
        if logging.root.isEnabledFor(logging.DEBUG):
            output_stream.write(line)  # Print to console in real-time

def call_executable(command: List[str], timeout: Optional[int] = None, output_type: ReturnContent = ReturnContent.BOOL) -> \
Union[str, bool, int]:
    command_string = " ".join(command)
    logging.info("Calling external command: %s", command_string)

    try:
        # result = subprocess.run(**args, check=True, capture_output=True, universal_newlines=True)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Lists to capture output
        stdout_lines = []
        stderr_lines = []
        # Threads for reading stdout and stderr
        stdout_thread = threading.Thread(target=_stream_output, args=(process.stdout, stdout_lines, sys.stdout))
        stderr_thread = threading.Thread(target=_stream_output, args=(process.stderr, stderr_lines, sys.stderr))
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the process to complete
        process.wait()

        # Wait for threads to complete
        stdout_thread.join()
        stderr_thread.join()

        # success
        return_code = process.returncode
        if return_code == 0:
            if output_type == ReturnContent.STDOUT:
                stdout_output = ''.join(stdout_lines)
                return stdout_output
            elif output_type == ReturnContent.BOOL:
                return True
            else:
                return return_code
        else:
            main_error = f"Executable run failed for command: {command_string}"
            logging.error(main_error)

            # stderr output
            if stderr_lines:
                logging.error("Executable stderr output START\n%s", ''.join(stderr_lines))
                logging.error("Executable stderr output END.")

            # exit code
            decoded = _decode_exit_status_code(return_code)
            if decoded:
                logging.info('Exit status code: %d: %s (%s)', decoded[0], decoded[1], decoded[3])
            else:
                logging.info("Exist status code: %d", return_code)

            # stdout output
            if stdout_lines:
                logging.error("Executable output START\n%s", ''.join(stdout_lines))
                logging.error("Executable output END.")

            # exception handling
            if output_type == ReturnContent.BOOL:
                return False
            raise RuntimeError(main_error)
    except OSError:
        logging.error("Executable %s not found. Check if the full path to the executable is in "
                      "the system PATH environment variable.", command[0])
        if output_type == ReturnContent.BOOL:
            return False
        raise

    # except subprocess.TimeoutExpired:
    #     logging.warning("Timeout expired (%d)", timeout)
    #     if output_type == ReturnContent.BOOL:
    #         return False
    #     raise
