"""json_utils tests."""

import datetime
import unittest

from bot.utils import json_utils


class JSONDumpsTest(unittest.TestCase):
  """Test json_utils.dumps."""

  def test(self):
    """Tests json_utils.dumps with various primitive data types."""
    self.assertEqual(json_utils.dumps('string'), '"string"')

    self.assertEqual(json_utils.dumps(True), 'true')
    self.assertEqual(json_utils.dumps(False), 'false')

    self.assertEqual(json_utils.dumps(-5), '-5')
    self.assertEqual(json_utils.dumps(0), '0')
    self.assertEqual(json_utils.dumps(10), '10')
    self.assertEqual(json_utils.dumps(12.0), '12.0')

    self.assertEqual(
        json_utils.dumps(datetime.datetime(2018, 2, 4, 1, 2, 3, 9)),
        '{"__type__": "datetime", "day": 4, "hour": 1, "microsecond": 9, '
        '"minute": 2, "month": 2, "second": 3, "year": 2018}')
    self.assertEqual(
        json_utils.dumps(datetime.date(2018, 3, 20)),
        '{"__type__": "date", "day": 20, "month": 3, "year": 2018}')


class JSONLoadsTest(unittest.TestCase):
  """Test json_utils.loads."""

  def test(self):
    """Tests json_utils.loads with various primitive data types."""
    self.assertEqual(json_utils.loads('"string"'), 'string')

    self.assertEqual(json_utils.loads('true'), True)
    self.assertEqual(json_utils.loads('false'), False)

    self.assertEqual(json_utils.loads('-5'), -5)
    self.assertEqual(json_utils.loads('0'), 0)
    self.assertEqual(json_utils.loads('10'), 10)
    self.assertEqual(json_utils.loads('12.0'), 12.0)

    self.assertEqual(
        json_utils.loads(
            '{"second": 3, "microsecond": 9, "hour": 1, "year": 2018, '
            '"__type__": "datetime", "day": 4, "minute": 2, "month": 2}'),
        datetime.datetime(2018, 2, 4, 1, 2, 3, 9))

    self.assertEqual(
        json_utils.loads(
            '{"__type__": "date", "day": 20, "month": 3, "year": 2018}'),
        datetime.date(2018, 3, 20))
