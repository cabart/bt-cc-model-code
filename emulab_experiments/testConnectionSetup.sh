#!/usr/bin/bash

# Maybe should add option to see what went wrong
echo "try connecting to server..."

export OPENSSL_CONF=$(realpath ./local_ssl.cnf)

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
	sudo -E ../env/bin/python ./serverCommunication.py
else
	sudo -E ../env/bin/python ./serverCommunication.py &> /dev/null
fi

if [ $? -eq 0 ]; then
    echo "Success: Connection to server did work!"
else
    echo "Fail: Connection to server not possible"
fi
