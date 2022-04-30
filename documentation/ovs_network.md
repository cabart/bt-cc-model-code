# OpenVSwitch Setup

This section explains how to setup a virtual switch using Open vSwitch software.

## Goal

Have a network of x senders, 1 OvS node and 1 receiver

1. Create network topology
2. Setup OvS node
3. Test network structure

## setup using VMs only

(Emulab) profile: VswitchNnodes
Network of n sender nodes, one receiver node and one node in between as switch (all VMs).

## OVS Setup

Switch setup is based on [OVS setup](https://groups.geni.net/geni/wiki/GENIExperimenter/Tutorials/OpenFlowOVS/DesignSetup)

1. Install OVS

        sudo apt update
        sudo apt install -y openvswitch-switch

2. Add bridge

        sudo ovs-vsctl add-br br0

3. For all connected devices (interfaces, eth1, eth2, ...)(except eth0 and lo obviously):

        sudo ifconfig eth1 0

4. Again for the same interfaces do:

        sudo ovs-vsctl add-port br0 eth1

5. Set mode (should be default and therefore optional):

        sudo ovs-vsctl set-fail-mode br0 standalone

6. (Optional) Check if setup correct:

        sudo ovs-vsctl show

### About step 5 (set mode)

If standalone mode is used, the virtual switch will setup its port forwarding table automatically. If 'secure' mode is used, a controller needs to be added to communicate with the virtual switch and to send the port forwarding table entries (should look into this).

For the simple setup of this experiment no controller is needed as the switch correctly sets up the network automatically

## Next Step: Automation

A script doing the OVS setup as described above is started at startup of the switch node. For details see [startup code](/emulab_experiments/remote_scripts/switch_ovs_startup.sh)

## Notes

To check if network setup is correct: Install nmap and do port search

        ~~~bash
        nmap -sP 192.168.1.1/24
        ~~~
