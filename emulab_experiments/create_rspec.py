# description is taken from main file
"""Creates a network of n sender nodes, one receiver node and one virtual switch inbetween to connect them.

Instructions:
Click on any node in the topology and choose the `shell` menu item. When your shell window appears, use `ping` to test the link.

"""

# Import the Portal object.
import geni.portal as portal
# Import the ProtoGENI library.
import geni.rspec.pg as pg
import geni.rspec.emulab as emulab

# global parameters
repoURL = "https://github.com/cabart/bt-cc-model-code/archive/main.tar.gz"
repoPath = "/local"

def createUnboundRspec(numSender, linkCapacity):
    """ Returns unbound rspec file as string """

    linkCapacity *= 1000 # in kilobytes # TODO: seems not to be true

    # Create a portal context.
    pc = portal.Context()

    # Create a Request object to start building the RSpec.
    #request = pc.makeRequestRSpec()
    request = pg.Request()

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
    mysw.exclusive = True # otherwise overall bandwith is limited, and port would not be 22
    mysw.disk_image = img
    mysw.installRootKeys(True,True)

    # TODO: Test this
    # give switch a public ip address, maybe not needed
    mysw.routable_control_ip = True

    # add startup services to switch
    mysw.addService(pg.Install(url=repoURL, path=repoPath))
    startupOVS = "/local/bt-cc-model-code-main/emulab_experiments/remote_scripts/switch_ovs_startup.sh -n " + str(numSender)
    mysw.addService(pg.Execute(shell="bash", command=startupOVS))

    startupSender = "/local/bt-cc-model-code-main/emulab_experiments/remote_scripts/node_startup.sh"

    rcviface = mysw.addInterface("rcv")
    rcviface.addAddress(pg.IPv4Address("10.0.0.1","255.255.255.0"))

    # set physical type of virtual switch
    if phystype != "":
        mysw.hardware_type = phystype

    # Add sender PC's
    for i in range(1,numSender+1):
        # create node + interface + address
        nodeName = "h" + str(i)
        node = request.RawPC(nodeName)
        node.disk_image = img
        node.installRootKeys(True,True)
        
        # set physical type of sender node
        if phystype != "":
            node.hardware_type = phystype
        node.addService(pg.Install(url=repoURL, path=repoPath))
        node.addService(pg.Execute(shell="bash", command=startupSender))
        
        iface = node.addInterface("sendIface" + str(i))
        iface.addAddress(pg.IPv4Address("10.0.0." + str(i+2),"255.255.255.0"))
        sendiface = mysw.addInterface("send" + str(i))
        sendiface.addAddress(pg.IPv4Address("10.0.0." + str(numSender+2+i),"255.255.255.0"))
        link = request.Link("sendLink-" + nodeName,members=[iface,sendiface])
        link.bandwidth = linkCapacity
        
    # receiver node
    rcvNode = request.RawPC("hDest")
    rcvNode.disk_image = img
    rcvNode.installRootKeys(True,True)
    rcvNode.addService(pg.Install(url=repoURL, path=repoPath))
    startupReceiver = "/local/bt-cc-model-code-main/emulab_experiments/remote_scripts/node_startup.sh"
    rcvNode.addService(pg.Execute(shell="bash", command=startupReceiver))

    # set physical type of receiver node
    if phystype != "":
        rcvNode.hardware_type = phystype

    iface = rcvNode.addInterface("rcv")
    iface.addAddress(pg.IPv4Address("10.0.0.2","255.255.255.0"))
    link = request.Link("rcvLink", members=[rcviface,iface])
    link.bandwidth = linkCapacity
    
    # Print the RSpec to the enclosing page.
    return request.toXMLString(pretty_print=True, ucode=True)