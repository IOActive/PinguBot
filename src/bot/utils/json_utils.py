
"""JSON helper utilities."""

import datetime
import json


class JSONEncoder(json.JSONEncoder):
  """Custom version of JSON encoder with support for additional object types
  (e.g. datetime)."""

  def default(self, o):  # pylint: disable=method-hidden
    if isinstance(o, datetime.datetime):
      return {
          '__type__': 'datetime',
          'year': o.year,
          'month': o.month,
          'day': o.day,
          'hour': o.hour,
          'minute': o.minute,
          'second': o.second,
          'microsecond': o.microsecond,
      }
    if isinstance(o, datetime.date):
      return {
          '__type__': 'date',
          'year': o.year,
          'month': o.month,
          'day': o.day,
      }

    return json.JSONEncoder.default(self, o)


class JSONDecoder(json.JSONDecoder):
  """Custom version of JSON decoder with support for additional object types
  (e.g. datetime)."""
  _TYPES = {'datetime': datetime.datetime, 'date': datetime.date}

  def __init__(self, *args, **kwargs):
    super(JSONDecoder, self).__init__(
        object_hook=self.dict_to_object, *args, **kwargs)

  def dict_to_object(self, d):
    if '__type__' not in d:
      return d

    object_type = d.pop('__type__')
    try:
      return self._TYPES[object_type](**d)
    except Exception:
      d['__type__'] = object_type
      return d


def dumps(obj, *args, **kwargs):
  """Custom json.dumps using custom encoder JSONEncoder defined in this file."""
  kwargs['cls'] = JSONEncoder
  kwargs['sort_keys'] = True
  return json.dumps(obj, *args, **kwargs)


def loads(obj, *args, **kwargs):
  """Custom json.loads using custom encoder JSONDecoder defined in this file."""
  kwargs['cls'] = JSONDecoder
  return json.loads(obj, *args, **kwargs)
