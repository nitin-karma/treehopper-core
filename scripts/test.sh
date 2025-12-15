#!/bin/bash
set -e

export TH_TEST_MODE=1
export TREEHOPPER_DEV_MODE=1

pytest -q --disable-warnings --maxfail=1
