#!/usr/bin/bash

echo "ovs setup script running..." >> /local/startup.log
ifconfig >> /local/startup.log

while getopts ":n:" flag
do
	case "${flag}" in
		n) sender=${OPTARG};;
	esac
done

echo "number of senders $sender" >> /local/startup.log
((sender++))
echo "number of total nodes $sender" >> /local/startup.log

sudo apt update
sudo apt install -y openvswitch-switch
sudo ovs-vsctl add-br br0

for i in $(seq 1 $sender);
do
	# maybe should add "2>> /tmp/startup.txt" to analyse potential errors
	sudo ifconfig eth$i 0 
done

for i in $(seq 1 $sender);
do
	# maybe should add "2>> /tmp/startup.txt" to analyse potential errors
	sudo ovs-vsctl add-port br0 eth$i
done

sudo ovs-vsctl set-fail-mode br0 standalone

sudo ovs-vsctl show > /tmp/switch_bridge.txt

echo "ovs setup complete!" >> /local/startup.log
