#!/usr/bin/bash

# Maybe should add option to see what went wrong
echo "try connecting to server..."

export OPENSSL_CONF=$(realpath ./local_ssl.cnf)
sudo -E ../env/bin/python ./serverCommunication.py &> /dev/null
#sudo -E ../env/bin/python ./serverCommunication.py
if [ $? -eq 0 ]; then
    echo "Success: Connection to server did work!"
else
    echo "Fail: Connection to server not possible"
fi
