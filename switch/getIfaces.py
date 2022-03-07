# Get the names of the interfaces of the switch
# Receiver should be at address 10.0.0.1
# Senders should be at address 10.0.0.x | x >= 5

def getSenderifaces():
    # get all interfaces (format: '<iface> <ip> <macaddress>')
    with open("/var/emulab/boot/ifmap",'r') as f:
        data = [x.split() for x in f.readlines()]

    # only keep ifaces connected to sender, not the one connected to receiver
    filtered = filter(lambda x: x[1] != "10.0.0.1", data)
    extendedIfaces = list(filtered)

    ifaces = []
    for i in extendedIfaces:
        ifaces.append(i[0])
    
    return ifaces

def getReceiveriface():
    # get all interfaces (format: '<iface> <ip> <macaddress>')
    with open("/var/emulab/boot/ifmap",'r') as f:
        data = [x.split() for x in f.readlines()]

    # only keep ifaces connected to sender, not the one connected to receiver
    filtered = filter(lambda x: x[1] == "10.0.0.1", data)
    extendedIfaces = list(filtered)

    iface = extendedIfaces[0][0]
    return iface
