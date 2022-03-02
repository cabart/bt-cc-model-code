#!/usr/bin/env bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
FILENAME="./getPort.py"

echo $SCRIPT_DIR
cd $SCRIPT_DIR
sudo python $FILENAME