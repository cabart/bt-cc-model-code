#!/usr/bin/bash
echo "new sender started:" >> /local/sender.log
hostname >> /local/sender.log

sudo apt-get update
sudo apt install -y python3-pip
pip install pandas
pip install matplotlib
pip install numpy