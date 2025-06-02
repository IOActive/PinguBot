
"""Custom init runner."""

import os

from pingu_sdk.metrics import logs
from pingu_sdk.system import environment, process_handler

SCRIPT_DIR = os.path.join('bot', 'init')


def _extension(platform):
    """Get the init extension for a platform."""
    if platform == 'windows':
        return '.ps1'

    return '.bash'


def run():
    """Run custom platform specific init scripts."""
    platform = environment.platform().lower()
    script_path = os.path.join(environment.get_config_directory(), SCRIPT_DIR,
                               platform + _extension(platform))
    if not os.path.exists(script_path):
        return

    os.chmod(script_path, 0o750)
    if script_path.endswith('.ps1'):
        cmd = 'powershell.exe ' + script_path
    else:
        cmd = script_path

    try:
        process_handler.run_process(
            cmd,
            timeout=1800,
            need_shell=True,
            testcase_run=False,
            ignore_children=True)
    except Exception:
        logs.log_error('Failed to execute platform initialization script.')
