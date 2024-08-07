
"""Constants shared across butler commands."""

import collections
import os
import sys

# Chromedriver related constants.
CHROMEDRIVER_VERSION_URL = (
    'https://commondatastorage.googleapis.com/chromedriver/LATEST_RELEASE_91')
CHROMEDRIVER_DOWNLOAD_PATTERN = (
    'https://commondatastorage.googleapis.com/chromedriver/{version}/'
    '{archive_name}')

# Local directory of deployment files.
PACKAGE_TARGET_ZIP_DIRECTORY = 'deployment'

# Deprecated source archive name.
LEGACY_ZIP_NAME = 'bot-source.zip'

# File containing the source revision information.
PACKAGE_TARGET_MANIFEST_PATH = os.path.join('src', 'appengine', 'resources',
                                            'bot-source.manifest')

# Supported Platforms and ABIS (newer to older order).
PLATFORMS = collections.OrderedDict([
    ('windows', 'win_amd64'),
    ('macos', ('macosx_10_14_x86_64', 'macosx_10_9_x86_64',
               'macosx_10_12_x86_64')),
    ('linux', ('manylinux2010_x86_64', 'manylinux1_x86_64')),
])

if sys.version_info.major == 3 and sys.version_info.minor == 7:
  ABIS = {'linux': 'cp37m', 'windows': 'cp37m', 'macos': 'cp37m'}
elif sys.version_info.major == 3 and sys.version_info.minor == 8:
  ABIS = {'linux': 'cp38', 'windows': 'cp38', 'macos': 'cp38'}
elif sys.version_info.major == 3 and sys.version_info.minor == 9:
  ABIS = {'linux': 'cp39', 'windows': 'cp39', 'macos': 'cp39'}
elif sys.version_info.major == 3 and sys.version_info.minor == 10:
  ABIS = {'linux': 'cp10', 'windows': 'cp10', 'macos': 'cp10'}
elif sys.version_info.major == 3 and sys.version_info.minor == 11:
  ABIS = {'linux': 'cp11', 'windows': 'cp11', 'macos': 'cp11'}
else:
  raise Exception('Only python versions 3.7-3.11 are supported.')

# Config directory to use for tests.
TEST_CONFIG_DIR = os.path.join('configs', 'test')

# Application id for local testing.
TEST_APP_ID = 'test-bot'
TEST_APP_ID_WITH_DEV_PREFIX = 'dev~' + TEST_APP_ID

DEV_APPSERVER_PORT = 9000
DEV_APPSERVER_HOST = 'localhost:' + str(DEV_APPSERVER_PORT)

CRON_SERVICE_PORT = 9009
CRON_SERVICE_HOST = 'localhost:' + str(CRON_SERVICE_PORT)

DEV_APPSERVER_ADMIN_PORT = 9002

DATASTORE_EMULATOR_PORT = 9004
DATASTORE_EMULATOR_HOST = 'localhost:' + str(DATASTORE_EMULATOR_PORT)

PUBSUB_EMULATOR_PORT = 9006
PUBSUB_EMULATOR_HOST = 'localhost:' + str(PUBSUB_EMULATOR_PORT)

LOCAL_GCS_SERVER_PORT = 9008
LOCAL_GCS_SERVER_HOST = 'http://localhost:' + str(LOCAL_GCS_SERVER_PORT)
