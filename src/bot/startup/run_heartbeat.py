
"""Heartbeat script wrapper."""

# Before any other imports, we must fix the path. Some libraries might expect
# to be able to import dependencies directly, but we must store these in
# subdirectories of common so that they are shared with App Engine.
from bot.datastore import data_handler
from bot.metrics import logs
from bot.system import environment, shell

import os
import subprocess
import sys


BEAT_SCRIPT = 'heartbeat.py'


def main():
    """Update the heartbeat if there is bot activity."""
    if len(sys.argv) < 2:
        print('Usage: %s <log file>' % sys.argv[0])
        return

    logs.configure('run_heartbeat')

    log_filename = sys.argv[1]
    previous_state = None

    # Get absolute path to heartbeat script and interpreter needed to execute it.
    startup_scripts_directory = environment.get_startup_scripts_directory()
    beat_script_path = os.path.join(startup_scripts_directory, BEAT_SCRIPT)
    beat_interpreter = shell.get_interpreter(beat_script_path)
    assert beat_interpreter

    while True:
        beat_command = [
            beat_interpreter, beat_script_path,
            str(previous_state), log_filename
        ]

        try:
            previous_state = subprocess.check_output(
                beat_command, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logs.log_error('Failed to beat.', output=e.output)
        except Exception as e:
            logs.log_error('Failed to beat.')

        # See if our run timed out, if yes bail out.
        if data_handler.bot_run_timed_out():
            break


if __name__ == '__main__':
       main()
