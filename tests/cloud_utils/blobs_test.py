
"""Tests for blobs."""

import os
import unittest

import mock

from bot.google_cloud_utils import blobs
from bot.tests.test_libs import helpers
from bot.tests.test_libs import test_utils

TEST_UUID = 'e612999f-ed89-4496-b4bd-3e8c7d8da18a'


@test_utils.with_cloud_emulators('datastore')
class BlobsTest(unittest.TestCase):
  """Tests for blobs."""

  def setUp(self):
    helpers.patch_environ(self)
    helpers.patch(self, [
        'bot.system.environment.is_running_on_app_engine',
        'bot.google_cloud_utils.blobs.generate_new_blob_name',
        'bot.google_cloud_utils.storage.copy_file_from',
        'bot.google_cloud_utils.storage.copy_file_to',
        'bot.google_cloud_utils.storage.delete',
        'bot.google_cloud_utils.storage.read_data',
        'bot.google_cloud_utils.storage.get',
    ])

    self.mock.is_running_on_app_engine.return_value = True
    os.environ['TEST_BLOBS_BUCKET'] = 'blobs-bucket'

    blobs.BlobInfo(
        id='legacyblobkey',
        filename='legacy-file',
        size=123,
        gs_object_name='/blobs-bucket/legacy').put()

    self.mock.get.return_value = {
        'metadata': {
            'filename': 'gcs-file',
        },
        'size': 456,
    }

    self.mock.is_running_on_app_engine.return_value = False
    self.mock.generate_new_blob_name.return_value = 'new-key'

    self.mock.copy_file_from.return_value = True
    self.mock.copy_file_to.return_value = True
    self.mock.read_data.return_value = b'data'
    self.mock.delete.return_value = True

  def test_get_gcs_path(self):
    """Test get_gcs_path."""
    self.assertEqual('/blobs-bucket/' + TEST_UUID,
                     blobs.get_gcs_path(TEST_UUID))

  def test_get_gcs_path_legacy(self):
    """Test get_gcs_path for legacy blobs."""
    self.assertEqual('/blobs-bucket/legacy',
                     blobs.get_gcs_path('legacyblobkey'))

  def test_get_blob_size_gcs(self):
    """Test get_blob_size for GCS blob."""
    self.assertEqual(456, blobs.get_blob_size(TEST_UUID))

  def test_get_blob_size_legacy(self):
    """Test get_blob_size for legacy blob."""
    self.assertEqual(123, blobs.get_blob_size('legacyblobkey'))

  def test_get_blob_size_invalid(self):
    """Test get_blob_size for invalid blob."""
    self.assertEqual(None, blobs.get_blob_size(None))
    self.assertEqual(None, blobs.get_blob_size('NA'))
    self.assertEqual(None, blobs.get_blob_size(''))

  def test_get_blob_info_gcs(self):
    """Test get_gcs_path for GCS files."""
    blob_info = blobs.get_blob_info(TEST_UUID)
    self.assertEqual(TEST_UUID, blob_info.key())
    self.assertEqual(456, blob_info.size)
    self.assertEqual('gcs-file', blob_info.filename)

  def test_get_blob_info_legacy(self):
    """Test get_gcs_path for legacy files."""
    blob_info = blobs.get_blob_info('legacyblobkey')
    self.assertEqual('legacyblobkey', blob_info.key())
    self.assertEqual(123, blob_info.size)
    self.assertEqual('legacy-file', blob_info.filename)

  def test_delete(self):
    """Test delete for GCS files."""
    self.assertEqual(True, blobs.delete_blob(TEST_UUID))
    self.mock.delete.assert_has_calls([
        mock.call('/blobs-bucket/' + TEST_UUID),
    ])

  def test_delete_legacy(self):
    """Test delete for legacy files."""
    self.assertEqual(True, blobs.delete_blob('legacyblobkey'))
    self.mock.delete.assert_has_calls([
        mock.call('/blobs-bucket/legacy'),
    ])

  def test_write_blob_file(self):
    """Test write_blob with a filename."""
    self.mock.get.return_value = None
    self.assertEqual('new-key', blobs.write_blob('/file'))
    self.mock.copy_file_to.assert_has_calls([
        mock.call(
            '/file', '/blobs-bucket/new-key', metadata={
                'filename': 'file',
            }),
    ])

  def test_write_blob_handle(self):
    """Test write_blob with a handle."""
    self.mock.get.return_value = None
    handle = mock.Mock()
    handle.name = 'filename'

    self.assertEqual('new-key', blobs.write_blob(handle))
    self.mock.copy_file_to.assert_has_calls([
        mock.call(
            handle, '/blobs-bucket/new-key', metadata={
                'filename': 'filename',
            }),
    ])

  def test_read_blob_to_disk(self):
    """Test read_blob_to_disk for GCS files."""
    self.assertTrue(blobs.read_blob_to_disk(TEST_UUID, '/file'))
    self.mock.copy_file_from.assert_has_calls([
        mock.call('/blobs-bucket/' + TEST_UUID, '/file'),
    ])

  def test_read_blob_to_disk_legacy(self):
    """Test read_blob_to_disk for legacy files."""
    self.assertTrue(blobs.read_blob_to_disk('legacyblobkey', '/file'))
    self.mock.copy_file_from.assert_has_calls([
        mock.call('/blobs-bucket/legacy', '/file'),
    ])

  def test_read_key(self):
    """Test read key for GCS files."""
    self.assertEqual(b'data', blobs.read_key(TEST_UUID))
    self.mock.read_data.assert_has_calls([
        mock.call('/blobs-bucket/' + TEST_UUID),
    ])

  def test_read_key_legacy(self):
    """Test read key for legacy files."""
    self.assertEqual(b'data', blobs.read_key('legacyblobkey'))
    self.mock.read_data.assert_has_calls([
        mock.call('/blobs-bucket/legacy'),
    ])
