#!/bin/bash

# Create a subdirectory under /g2s/workflows

subdir=$1
wf_file=$2
exec_config=$3

# Create subdirectory for the workflow and copy the two files. Create also a directory for test data
mkdir /g2s/workflows/$subdir
mkdir /g2s/workflows/$subdir/test_data

cp "$wf_file" /g2s/workflows/$subdir
cp "$exec_config" /g2s/workflows/$subdir

