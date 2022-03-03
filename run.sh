#!/usr/bin/bash

# TODO add flag for config file
echo "Start emulab experiment"

# export OPENSSL_CONF=$(realpath ./emulab_experiments/local_ssl2.cnf)

# check for verbose flag
while getopts ":v" opt; do
	case $opt in
		v)
			echo "Use verbose output"
			verbose=true
			;;
		\?)
			echo "Invalid option: -$OPTARG"
			exit 1
			;;
		:)
			echo "Don't use verbose output"	
			verbose=false
			;;
	esac
done

if [ "$verbose" = true ]
then
	sudo ./env/bin/python ./emulab_experiments/run_emulab_experiment.py ./configs/test_config.yml
	#sudo ./env/bin/python ./emulab_experiments/run_emulab_experiment.py ./configs/big_experiment.yaml
else
	sudo -E ./env/bin/python ./emulab_experiments/run_emulab_experiment.py ./configs/test_config.yml &> /dev/null
fi

if [ $? -eq 0 ]; then
    echo "Success: Experiment ended successfully"
else
    echo "Fail: Experiment failed"
fi
