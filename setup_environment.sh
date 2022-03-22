#!/bin/bash
# install geni-lib package in python virtual environment

if [ "$EUID" -ne 0 ]
  then echo "Please run as root (needed for system packages to install)"
  exit
fi

env/bin/python -m pip install ./geni-lib/
env/bin/python -m pip install -r requirements/requirements.txt

sudo apt update
sudo apt install -y texlive-latex-extra cm-super dvipng