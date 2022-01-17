# description is taken from main file
"""Creates a network of n sender nodes, one receiver node and one virtual switch inbetween to connect them.

Instructions:
Click on any node in the topology and choose the `shell` menu item. When your shell window appears, use `ping` to test the link.

"""

# Import the Portal object.
import geni.portal as portal
# Import the ProtoGENI library.
import geni.rspec.pg as pg

# global parameters
repoURL = "https://github.com/cabart/bt-cc-model-code/archive/main.tar.gz"
repoPath = "/local"

def createUnboundRspec(config):
    sendDuration = config['send_duration']
    numSender = config['inferred']['num_senders']
    linkCapacity = config['link_capacity'] * 1000   # in kilobytes
    # ... more parameters

    # Create a portal context.
    pc = portal.Context()

    # Create a Request object to start building the RSpec.
    request = pc.makeRequestRSpec()

    # physical type of all nodes
    # TODO: add this to experiment parameter
    
    physList = [
        ('', 'let resource mapper choose'),
        ('d710', 'd710, <6Gb'),
        ('d430', 'd430, <40Gb'),
        ('d820', 'd820, <20Gb (not recommended, only 16 nodes in network)'),
        ('pc3000', 'pc3000, <5Gb (not tested yet')
    ]
    phystype = physList[0][0]

    # Use Ubuntu 20.04
    img = 'urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU20-64-STD'

    # Add Switch to the request
    mysw = request.XenVM("switch")
    mysw.exclusive = True
    mysw.disk_image = img

    # give switch a public ip address, maybe not needed
    mysw.routable_control_ip = True

    # add startup services to switch
    mysw.addService(pg.Install(url=repoURL, path=repoPath))
    startupOVS = "/local/bt-cc-model-code-main/switch/ovs_startup.sh -n " + str(numSender)
    mysw.addService(pg.Execute(shell="bash", command=startupOVS))

    startupSender = "/local/bt-cc-model-code-main/sender/sender_startup.sh"

    rcviface = mysw.addInterface("eth2")
    rcviface.addAddress(pg.IPv4Address("192.168.1.1","255.255.255.0"))

    # set physical type of virtual switch
    if phystype != "":
        mysw.hardware_type = phystype

    # Add sender PC's
    for i in range(numSender):
        # create node + interface + address
        nodeName = "sender" + str(i)
        node = request.RawPC(nodeName)
        node.disk_image = img
        
        # set physical type of sender node
        if phystype != "":
            node.hardware_type = phystype
        node.addService(pg.Install(url=repoURL, path=repoPath))
        node.addService(pg.Execute(shell="bash", command=startupSender))
        
        iface = node.addInterface("eth1")
        iface.addAddress(pg.IPv4Address("192.168.1." + str(i+3),"255.255.255.0"))
        sendiface = mysw.addInterface()
        sendiface.addAddress(pg.IPv4Address("192.168.1." + str(numSender+3+i),"255.255.255.0"))
        link = request.Link("sendLink-" + str(i),members=[iface,sendiface])
        link.bandwidth = linkCapacity
        
    # receiver node
    rcvNode = request.RawPC("receiver")
    rcvNode.disk_image = img
    rcvNode.addService(pg.Install(url=repoURL, path=repoPath))

    # set physical type of receiver node
    if phystype != "":
        rcvNode.hardware_type = phystype

    iface = rcvNode.addInterface("eth2")
    iface.addAddress(pg.IPv4Address("192.168.1.2","255.255.255.0"))
    link = request.Link("rcvLink", members=[rcviface,iface])
    link.bandwidth = linkCapacity
    
    # Print the RSpec to the enclosing page.
    #pc.printRequestRSpec(request)
    return request