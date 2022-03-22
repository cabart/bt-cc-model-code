#!/usr/bin/bash

echo "net.core.default_qdisc=fq" | sudo tee -a /etc/sysctl.conf | sudo tee -a /local/node.log >> /dev/null
echo "net.ipv4.tcp_congestion_control=bbr" | sudo tee -a /etc/sysctl.conf | sudo tee -a /local/node.log >> /dev/null
sudo sysctl -p >> /dev/null
sysctl net.ipv4.tcp_available_congestion_control | sudo tee -a /local/node.log