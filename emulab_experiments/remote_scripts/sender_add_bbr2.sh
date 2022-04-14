#!/usr/bin/bash

# Install liquorix kernel to add bbr2 support
# https://liquorix.net/ for more information about the kernel

#sudo add-apt-repository -y ppa:damentz/liquorix | sudo tee -a /local/node.log >> /dev/null
sudo add-apt-repository -y ppa:damentz/liquorix >> /dev/null
code1=$?
#sudo apt-get update | sudo tee -a /local/node.log >> /dev/null
sudo apt-get update >> /dev/null
code2=$?
#sudo apt-get install -y linux-image-liquorix-amd64 linux-headers-liquorix-amd64 | sudo tee -a /local/node.log >> /dev/null
sudo apt-get install -y linux-image-liquorix-amd64 linux-headers-liquorix-amd64 >> /dev/null
code3=$?
echo "$code1,$code2,$code3,AllDoneBBR2"