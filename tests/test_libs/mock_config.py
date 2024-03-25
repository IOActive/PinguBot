
"""Mock config."""


class MockConfig(object):
  """Mock config."""

  def __init__(self, data):
    self._data = data

  def get(self, key_name='', default=None):
    """Get key value using a key name."""
    parts = key_name.split('.')
    value = self._data
    for part in parts:
      if part not in value:
        return default

      value = value[part]

    return value

  def sub_config(self, path):
    return MockConfig(self.get(path))
