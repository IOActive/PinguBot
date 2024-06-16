# Copyright 2024 IOActive
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

from unittest import TestCase

from bot.datastore.storage import MinioProvider
from bot.system import environment


class TestMinioProvider(TestCase):
    def test__chunk_size(self):
        self.fail()

    def test_create_bucket(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        r = provider.create_bucket('test2')
        assert r is True

    def test_get_bucket(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        bucket = provider.get_bucket('test')
        assert bucket is not None

    def test_list_blobs(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        properties = provider.list_blobs('test')
        assert len(properties) > 0

    def test_copy_file_from(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        r = provider.copy_file_from("/test/test2/values.yaml", "../../../../bot/tmp/")
        assert r is True

    def test_copy_file_to(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        r = provider.copy_file_to("../../../../bot/tmp/test2/values.yaml", "/test/test2/values2.yaml")
        assert r is True

    def test_copy_blob(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        r = provider.copy_blob("/test/test2/values.yaml", "/test/values2.yaml")
        assert r is True

    def test_read_data(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        data = provider.read_data("/test/test2/values.yaml")
        assert len(data) > 0

    def test_write_data(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        r = provider.write_data(remote_path="/test/target.list", data="openssl-1.0.1f.zip")
        assert r is True

    def test_get(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        r = provider.get(remote_path="/test/test2/values.yaml")
        assert r is not None

    def test_delete(self):
        environment.load_cfg("../../startup/bot.cfg")
        provider = MinioProvider()
        r = provider.delete(remote_path="/test/test2/values.yaml")
        assert r is True
