# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Butler is here to help you with command-line tasks (e.g. running unit tests,
   deploying).

   You should code a task in Butler if any of the belows is true:
   - you run multiple commands to achieve the task.
   - you keep forgetting how to achieve the task.

   Please do `python butler.py --help` to see what Butler can help you.
"""

import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# guard needs to be at the top because it checks Python dependecies.
from local.butler import guard

guard.check()


class _ArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser."""

    def __init__(self, *args, **kwargs):
        """Override formatter_class to show default argument values in message."""
        kwargs['formatter_class'] = argparse.ArgumentDefaultsHelpFormatter
        argparse.ArgumentParser.__init__(self, *args, **kwargs)

    def error(self, message):
        """Override to print full help for ever error."""
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)

def main():
    """Parse the command-line args and invoke the right command."""
    parser = _ArgumentParser(
        description='Butler is here to help you with command-line tasks.')
    subparsers = parser.add_subparsers(dest='command')

    parser_run_bot = subparsers.add_parser(
        'run_bot', help='Run a local bot bot.')

    parser_run_bot.add_argument(
        '-c', '--config-dir', required=True, help='Path to application config.')
    parser_run_bot.add_argument(
        '--name', default='test-bot', help='Name of the bot.')
    parser_run_bot.add_argument(
        '--server-storage-path',
        default='local/storage',
        help='Server storage path.')
    parser_run_bot.add_argument('directory', help='Directory to create bot in.')
    parser_run_bot.add_argument(
        '--android-serial',
        help='Serial number of an Android device to connect to instead of '
             'running normally.')
    parser_run_bot.add_argument('--testing', dest='testing', action='store_true')


    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    _setup()
    command = importlib.import_module('local.butler.%s' % args.command)
    command.execute(args)


def _setup():
    """Set up configs and import paths."""
    os.environ['ROOT_DIR'] = os.path.abspath('.')
    os.environ['PYTHONIOENCODING'] = 'UTF-8'

    sys.path.insert(0, os.path.abspath(os.path.join('src')))
    from bot.system import modules
    modules.fix_module_search_paths()


if __name__ == '__main__':
    main()
