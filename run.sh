#!/usr/bin/bash

sudo ./env/bin/python ./emulab_experiments/run_emulab_experiment.py "$@"

if [ $? -eq 0 ]; then
    echo "Success: Experiment ended successfully"
else
    echo "Fail: Experiment failed"
fi
