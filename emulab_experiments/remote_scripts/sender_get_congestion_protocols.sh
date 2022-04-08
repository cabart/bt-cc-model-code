#!/usr/bin/bash
sysctl net.ipv4.tcp_available_congestion_control | sudo tee -a /local/node.log