#!/usr/bin/bash

# Install liquorix kernel to add bbr2 support
# https://liquorix.net/ for more information about the kernel
sudo add-apt-repository -y ppa:damentz/liquorix
sudo apt update
sudo apt install -y linux-image-liquorix-amd64 linux-headers-liquorix-amd64
sudo reboot