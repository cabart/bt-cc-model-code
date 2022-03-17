#!/usr/bin/bash
echo "new node started:" >> /local/node.log
hostname >> /local/node.log

sudo apt-get update
sudo apt install -y python3-pip
sudo pip install pandas
sudo pip install matplotlib
sudo pip install numpy
echo "Pip and libraries installed" >> /local/node.log