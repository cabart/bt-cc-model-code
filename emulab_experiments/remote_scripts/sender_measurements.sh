#!/usr/bin/env bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
FILENAME="./sender_measurements.py"

cd $SCRIPT_DIR
sudo python $FILENAME