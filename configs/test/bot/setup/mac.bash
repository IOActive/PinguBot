#!/bin/bash -e
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

if [ -z "$CLOUD_PROJECT_ID" ]; then
  echo "\$CLOUD_PROJECT_ID is not set."
  exit 1
fi

if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
  echo "\$GOOGLE_APPLICATION_CREDENTIALS is not set."
  exit 1
fi

NFS_ROOT=  # Fill in NFS information if available.
GOOGLE_CLOUD_SDK=google-cloud-sdk
GOOGLE_CLOUD_SDK_ARCHIVE=google-cloud-sdk-232.0.0-darwin-x86_64.tar.gz
INSTALL_DIRECTORY=${INSTALL_DIRECTORY:-${HOME}}
DEPLOYMENT_BUCKET=${DEPLOYMENT_BUCKET:-"deployment.$CLOUD_PROJECT_ID.appspot.com"}
DEPLOYMENT_ZIP="macos-3.zip"
GSUTIL_PATH="$INSTALL_DIRECTORY/$GOOGLE_CLOUD_SDK/bin"
ROOT_DIR="$INSTALL_DIRECTORY/clusterfuzz"
PYTHONPATH="$PYTHONPATH:$ROOT_DIR/src"

echo "Disabling macOS crash reporting (requires sudo)."
sudo -u $USER bash -c "launchctl unload -w /System/Library/LaunchAgents/com.apple.ReportCrash.plist"
sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.ReportCrash.Root.plist

echo "Disabling kernel message logging (requires sudo)."
sudo sysctl -w vm.shared_region_unnest_logging=0

echo "Increasing default file limit (requires sudo)."
sudo launchctl limit maxfiles 2048 unlimited
sudo ulimit -n 4096

echo "Creating directory $INSTALL_DIRECTORY."
if [ ! -d "$INSTALL_DIRECTORY" ]; then
  mkdir -p "$INSTALL_DIRECTORY"
fi

cd $INSTALL_DIRECTORY

echo "Fetching Google Cloud SDK."
if [ ! -d "$INSTALL_DIRECTORY/$GOOGLE_CLOUD_SDK" ]; then
  curl -O "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/$GOOGLE_CLOUD_SDK_ARCHIVE"
  tar -xzf $GOOGLE_CLOUD_SDK_ARCHIVE
  rm $GOOGLE_CLOUD_SDK_ARCHIVE
fi

echo "Activating credentials with the Google Cloud SDK."
$GSUTIL_PATH/gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS

echo "Specifying the proper Boto configuration file."

# Otherwise, gsutil will error out due to multiple types of configured
# credentials. For more information about this, see
# https://cloud.google.com/storage/docs/gsutil/commands/config#configuration-file-selection-procedure
BOTO_CONFIG_PATH=$($GSUTIL_PATH/gsutil -D 2>&1 | grep "config_file_list" | egrep -o "/[^']+gserviceaccount\.com/\.boto")

if [ -f $BOTO_CONFIG_PATH ]; then
  export BOTO_CONFIG="$BOTO_CONFIG_PATH"
else
  echo "WARNING: failed to identify the Boto configuration file and specify BOTO_CONFIG env."
fi

echo "Downloading ClusterFuzz source code."
rm -rf fuzzBot
$GSUTIL_PATH/gsutil cp gs://$DEPLOYMENT_BUCKET/$DEPLOYMENT_ZIP fuzzBot-source.zip
unzip -q fuzzBot-source.zip

echo "Installing ClusterFuzz package dependencies using pipenv."
cd fuzzBot
if ! python3 -m pip > /dev/null ; then
  curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
  python3 get-pip.py
fi
python3 -m pip install --upgrade pipenv
pipenv --python 3.7
pipenv sync
source "$(pipenv --venv)/bin/activate"

echo "Running ClusterFuzz."
NFS_ROOT="$NFS_ROOT" GOOGLE_APPLICATION_CREDENTIALS="$GOOGLE_APPLICATION_CREDENTIALS" ROOT_DIR="$ROOT_DIR" PYTHONPATH="$PYTHONPATH" GSUTIL_PATH="$GSUTIL_PATH" python $ROOT_DIR/src/python/bot/startup/run.py &

echo "Success!"
