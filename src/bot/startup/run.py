
"""Start the bot and heartbeat scripts."""

# Before any other imports, we must fix the path. Some libraries might expect
# to be able to import dependencies directly, but we must store these in
# subdirectories of common so that they are shared with App Engine.

# from bot._internal.base import modules

import atexit
import multiprocessing
import os
import subprocess
import time
import traceback

from bot.datastore import data_handler
from bot.metrics import logs
from bot.system import environment, shell

# modules.fix_module_search_paths()

BOT_SCRIPT = 'startup/run_bot.py'
HEARTBEAT_SCRIPT = 'startup/run_heartbeat.py'
HEARTBEAT_START_WAIT_TIME = 60
LOOP_SLEEP_INTERVAL = 3
MAX_SUBPROCESS_TIMEOUT = 2 ** 31 // 1000  # https://bugs.python.org/issue20493

_heartbeat_handle = None


def start_bot(bot_command):
    """Start the bot process."""
    command = shell.get_command(bot_command)

    # Wait until the process terminates or until run timed out.
    run_timeout = environment.get_value('RUN_TIMEOUT')
    if run_timeout and run_timeout > MAX_SUBPROCESS_TIMEOUT:
        # logs.log_error(
        #    'Capping RUN_TIMEOUT to max allowed value: %d' % MAX_SUBPROCESS_TIMEOUT)
        run_timeout = MAX_SUBPROCESS_TIMEOUT

    try:
        result = subprocess.run(
            command,
            timeout=run_timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False)
        exit_code = result.returncode
        output = result.stdout
    except subprocess.TimeoutExpired as e:
        exit_code = 0
        output = e.stdout
    except Exception:
        logs.log_error('Unable to start bot process (%s).' % bot_command)
        return 1

    if output:
        output = output.decode('utf-8', errors='ignore')
    log_message = f'Command: {command} (exit={exit_code})\n{output}'

    if exit_code == 0:
        logs.log(log_message)
    elif exit_code == 1:
        # Anecdotally, exit=1 means there's a fatal Python exception.
        logs.log_error(log_message)
    else:
        logs.log_warn(log_message)

    return exit_code


def sleep(seconds):
    """time.sleep wrapper for mocking."""
    time.sleep(seconds)


def start_heartbeat(heartbeat_command):
    """Start the heartbeat (in another process)."""
    global _heartbeat_handle
    if _heartbeat_handle:
        # If heartbeat is already started, no work to do. Bail out.
        return

    try:
        command = shell.get_command(heartbeat_command)
        process_handle = subprocess.Popen(command)  # pylint: disable=consider-using-with
    except Exception:
        logs.log_error(
            'Unable to start heartbeat process (%s).' % heartbeat_command)
        return

    # If heartbeat is successfully started, set its handle now.
    _heartbeat_handle = process_handle

    # Artificial delay to let heartbeat's start time update first.
    sleep(HEARTBEAT_START_WAIT_TIME)


def stop_heartbeat():
    """Stop the heartbeat process."""
    global _heartbeat_handle
    if not _heartbeat_handle:
        # If there is no heartbeat started yet, no work to do. Bail out.
        return

    try:
        _heartbeat_handle.kill()
    except Exception:
        pass

    _heartbeat_handle = None


def run_loop(bot_command, heartbeat_command):
    """Run infinite loop with bot's command."""
    atexit.register(stop_heartbeat)

    while True:
        start_heartbeat(heartbeat_command)
        start_bot(bot_command)

        # See if our run timed out, if yes bail out.
        try:
            if data_handler.bot_run_timed_out():
                break
        except Exception:
            logs.log_error('Failed to check for bot run timeout.')

        sleep(LOOP_SLEEP_INTERVAL)


def set_start_time():
    """Set START_TIME."""
    environment.set_value('START_TIME', time.time())


def main():
    set_start_time()
    root_directory = environment.get_value('ROOT_DIR')
    if not root_directory:
        print('Please set ROOT_DIR environment variable to the root of the source '
            'checkout before running. Exiting.')
        print('For an example, check init.bash in the local directory.')
        return
    
    environment.set_bot_environment()

    # Python buffering can otherwise cause exception logs in the child run_*.py
    # processes to be lost.
    environment.set_value('PYTHONUNBUFFERED', 1)

    # Create command strings to launch bot and heartbeat.
    log_directory = environment.get_value('LOG_DIR')
    bot_log = os.path.join(log_directory, 'bot.log')
    base_directory = environment.get_value('BASE_DIR')

    bot_script_path = os.path.join(base_directory, BOT_SCRIPT)
    bot_interpreter = shell.get_interpreter(BOT_SCRIPT)
    assert bot_interpreter
    bot_command = '%s %s' % (bot_interpreter, bot_script_path)

    heartbeat_script_path = os.path.join(base_directory, HEARTBEAT_SCRIPT)
    heartbeat_interpreter = shell.get_interpreter(HEARTBEAT_SCRIPT)
    assert heartbeat_interpreter
    heartbeat_command = '%s %s %s' % (heartbeat_interpreter,
                                      heartbeat_script_path, bot_log)

    run_loop(bot_command, heartbeat_command)

    logs.log('Exit run.py')


if __name__ == '__main__':
    multiprocessing.set_start_method('spawn')

    try:
        main()
        exit_code = 0
    except Exception as e:
        traceback.print_exc()
        exit_code = 1
