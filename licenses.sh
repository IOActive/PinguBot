#!/bin/bash

# find all .py files
files=$(find . -name "*.py" -type f)

# open each file and insert the license header
for file in $files; do
  if ! grep -q Copyright $file
  then
      cat copyright.txt $file >$file.new && mv $file.new $file
  fi
done