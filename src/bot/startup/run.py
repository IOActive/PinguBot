
"""Start the bot and heartbeat scripts."""

# Before any other imports, we must fix the path. Some libraries might expect
# to be able to import dependencies directly, but we must store these in
# subdirectories of common so that they are shared with App Engine.

# from bot._internal.base import modules

import atexit
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import os
import subprocess
import time
import traceback

from pingu_sdk.datastore import data_handler
from pingu_sdk.metrics import logs
from pingu_sdk.system import environment, shell
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client
from pingu_sdk.datastore.pingu_api.pingu_api import PinguAPIError

BOT_SCRIPT = 'startup/run_bot.py'
HEARTBEAT_SCRIPT = 'startup/run_heartbeat.py'
ANDROID_HEARTBEAT_SCRIPT = 'startup/android_heartbeat.py'
HEARTBEAT_START_WAIT_TIME = 60
LOOP_SLEEP_INTERVAL = 3
MAX_SUBPROCESS_TIMEOUT = 2 ** 31 // 1000

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

def start_android_heartbeat():
  """Start the android heartbeat (in another process)."""
  global _android_heartbeat_handle
  if _android_heartbeat_handle:
    # If heartbeat is already started, no work to do. Bail out.
    return

  base_directory = environment.get_startup_scripts_directory()
  android_beat_script_path = os.path.join(base_directory, ANDROID_HEARTBEAT_SCRIPT)
  android_beat_interpreter = shell.get_interpreter(android_beat_script_path)
  assert android_beat_interpreter
  android_beat_command = [android_beat_interpreter, android_beat_script_path]

  try:
    process_handle = subprocess.Popen(android_beat_command)
  except Exception:
    logs.log_error('Unable to start android heartbeat process (%s).' %
               android_beat_command)
    return

  # If heartbeat is successfully started, set its handle now.
  _android_heartbeat_handle = process_handle

def stop_android_heartbeat():
  """Stop the android heartbeat process."""
  global _android_heartbeat_handle
  if not _android_heartbeat_handle:
    # If there is no heartbeat started yet, no work to do. Bail out.
    return

  try:
    _android_heartbeat_handle.kill()
  except Exception as e:
    logs.log_error('Unable to stop android heartbeat process: %s' % str(e))

  _android_heartbeat_handle = None

def run_loop(bot_command, heartbeat_command):
    """Run infinite loop with bot's command."""
    atexit.register(stop_heartbeat)
    if environment.is_android():
        atexit.register(stop_android_heartbeat)

    while True:
        if environment.is_android():
            start_android_heartbeat()

        with ThreadPoolExecutor() as executor:
            future1 = executor.submit(start_heartbeat, heartbeat_command)
            future2 = executor.submit(start_bot, bot_command)

            # Wait for the first task to complete (heartbeat), if it finishes first, we will handle its result/exception
            try:
                future1.result()
            except Exception as e:
                logs.log_error('Failed to start heartbeat: {}'.format(e))

            # The second task (start_bot) might still be running or finished by now, we don't care about its result here

        exit_code = future2.result()  # Get the exit code of the bot
        logs.log(f'Job exited with code: {exit_code}. Exiting.')
        
        try:
            if data_handler.bot_run_timed_out():
                break
        except Exception:
            logs.log_error('Failed to check for bot run timeout.')


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
    
    # Ensure that The API host and API key are configured in the context
    if not environment.get_value("PINGUAPI_HOST") and not environment.get_value("PINGUAPI_KEY"):
        raise Exception("PINGU_HOST and PINGU_KEY must be set in the environment.")
    
    # Download latest bot configuration and update the context
    api_client = get_api_client()
    try:
        bot = api_client.bot_api.get_bot(bot_name=environment.get_value("BOT_NAME"))
        bot_configuration = api_client.bot_config_api.get_configuration(bot_id=bot.id)
        config_path = os.path.join(environment.get_value('ROOT_DIR'), 'config', 'bot', 'config.yaml')
        with open(config_path, "w")as config_file:
            config_file.write(bot_configuration.config_data)
        environment.set_default_vars()
    except PinguAPIError as e:
        logs.log_error("Failed to fetch bot configuration from Pingu API.")

    # Python buffering can otherwise cause exception logs in the child run_*.py
    # processes to be lost.
    environment.set_value('PYTHONUNBUFFERED', 1)

    # Create command strings to launch bot and heartbeat.
    log_directory = environment.get_value('LOG_DIR')
    #bot_log = os.path.join(log_directory, 'bot.log')
    base_directory = environment.get_value('BASE_DIR')

    bot_script_path = os.path.join(base_directory, BOT_SCRIPT)
    bot_interpreter = shell.get_interpreter(BOT_SCRIPT)
    assert bot_interpreter
    bot_command = '%s %s' % (bot_interpreter, bot_script_path)

    heartbeat_script_path = os.path.join(base_directory, HEARTBEAT_SCRIPT)
    heartbeat_interpreter = shell.get_interpreter(HEARTBEAT_SCRIPT)
    assert heartbeat_interpreter
    heartbeat_command = '%s %s %s' % (heartbeat_interpreter,
                                      heartbeat_script_path, log_directory)

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
