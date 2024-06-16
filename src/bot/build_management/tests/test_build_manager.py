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

from bot.build_management.build_manager import Build
from bot.system import environment


class TestBuild(TestCase):
    def test__build_targets(self):
        b = Build(
            "/home/roboboy/Projects/LuckyCAT/bot/builds/127.0.0.1:9001_test_770807ff2d8d31b43785f87303e8a91a87120e40/",
            '101')
        b._build_targets(
            path="/home/roboboy/Projects/LuckyCAT/bot/builds/127.0.0.1"
                 ":9001_test_770807ff2d8d31b43785f87303e8a91a87120e40/revisions/Build.sh")

    def test__build_targets_minijail(self):
        b = Build(
            "/home/roboboy/Projects/LuckyCAT/bot/builds/127.0.0.1:9001_test_770807ff2d8d31b43785f87303e8a91a87120e40/",
            '101')
        environment.load_cfg("../../startup/bot.cfg")
        b._build_targets_minijail(
            path="/home/roboboy/Projects/LuckyCAT/bot/builds/127.0.0.1"
                 ":9001_test_770807ff2d8d31b43785f87303e8a91a87120e40/revisions/Build.sh")
