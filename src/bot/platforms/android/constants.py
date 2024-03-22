
"""Common constants."""

import re

CRASH_DUMPS_DIR = '/sdcard/crash-reports'

DEVICE_DOWNLOAD_DIR = '/sdcard/Download'

DEVICE_TESTCASES_DIR = '/sdcard/fuzzer-testcases'

DEVICE_TMP_DIR = '/data/local/tmp'

# Directory to keep fuzzing artifacts for grey-box fuzzers e.g. corpus.
DEVICE_FUZZING_DIR = '/data/fuzz'

# The format of logcat when lowmemorykiller kills a process. See:
# https://android.googlesource.com/platform/system/core/+/master/lmkd/lmkd.c#586
LOW_MEMORY_REGEX = re.compile(
    r'Low on memory:|'
    r'lowmemorykiller: Killing|'
    r'to\s+free.*because\s+cache.*is\s+below\s+limit.*for\s+oom_', re.DOTALL)

# Various persistent cached values.
BUILD_PROP_MD5_KEY = 'android_build_prop_md5'
LAST_TEST_ACCOUNT_CHECK_KEY = 'android_last_test_account_check'
LAST_FLASH_BUILD_KEY = 'android_last_flash'
LAST_FLASH_TIME_KEY = 'android_last_flash_time'

PRODUCT_TO_KERNEL = {
    'blueline': 'bluecross',
    'crosshatch': 'bluecross',
    'flame': 'floral',
    'coral': 'floral',
    'walleye': 'wahoo',
    'muskie': 'wahoo',
    'taimen': 'wahoo',
}
