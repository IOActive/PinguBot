
"""Get values from the global configuration."""

import base64

from bot.datastore import data_types
from bot.system import environment

BASE64_MARKER = 'base64;'


def get():
    """Return configuration data."""
    # The reproduce tool does not have access to datastore. Rather than try to
    # catch all uses and handle them individually, we catch any accesses here.
    if environment.get_value('REPRODUCE_TOOL'):
        return None

    return data_types.Config.query().get()


def get_value(key):
    """Return a configuration key value."""
    config = get()
    if not config:
        return None

    value = config.__getattribute__(key)

    # Decode if the value is base64 encoded.
    if value.startswith(BASE64_MARKER):
        return base64.b64decode(value[len(BASE64_MARKER):])

    return value


def get_value_for_job(data, target_job_type):
    """Parses a value for a particular job type. If job type is not found,
  return the default value."""
    # All data is in a single line, just return that.
    if ';' not in data:
        return data

    result = ''
    for line in data.splitlines():
        job_type, value = (line.strip()).split(';')
        if job_type == target_job_type or (job_type == 'default' and not result):
            result = value

    return result


def set_value(key, value):
    """Sets a configuration key value and commits change."""
    config = get()
    if not config:
        return

    try:
        config.__setattr__(key, value)
    except UnicodeDecodeError:
        value = '%s%s' % (BASE64_MARKER, base64.b64encode(value))
        config.__setattr__(key, value)

    config.put()
