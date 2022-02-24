# OpenVSwitch Setup

## Goal

Have a network of x senders, 1 OVS node and 1 receiver

1. Create network topology
2. Setup OVS node
3. Test network structure

## setup using VMs only

profile: VswitchNnodes
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

Is a controller neccessary for our type of network?

## Next Step: Automation


## Notes

To check if network setup is correct: Install nmap and do port search

    nmap -sP 192.168.1.1/24

---

To test the network performance using iperf use the script in local/automation-tests/runExpssh.sh.
This runs iperf on all sender nodes (more or less simultaneously).
TODO: 

- solve authentication key issue
- parameterize for number of sender
- parameterize for the experiment name

---

ovs.addService(rspec.Execute(shell="bash", command="sudo %s" % GLOBALS.ovsscmd))