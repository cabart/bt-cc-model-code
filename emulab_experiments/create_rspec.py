# description is taken from main file
"""Creates a network of n sender nodes, one receiver node and one virtual switch inbetween to connect them.

Instructions:
Click on any node in the topology and choose the `shell` menu item. When your shell window appears, use `ping` to test the link.

"""

# Import the Portal object.
import geni.portal as portal
# Import the ProtoGENI library.
import geni.rspec.pg as pg
# Import Emulab library, only need for special extensions
# See: https://docs.cloudlab.us/geni-lib/api/genirspec/index.html
import geni.rspec.emulab as emulab

import logging
logger = logging.getLogger("root.create_rspec")

# global parameters
repoURL = "https://github.com/cabart/bt-cc-model-code/archive/main.tar.gz"
repoPath = "/local"

def createUnboundRspec(numSender, linkCapacity):
    '''
        Returns unbound rspec file as string

        Args:
            numSender: number of sender nodes
            linkCapacity: capacity of link, will be ignored

        Returns:
            String of rspec 'file'
    '''

    # Always request 1Gb links since Emulab anyway uses the next bigger
    # interface capacity and slows down the links using traffic controller
    linkCapacity = 1000000
    logger.info(f"requested link capacity: {linkCapacity}kb")

    # Use this if you really want the 'correct' capacity
    # Be aware that you are not guaranteed to get this capacity,
    # it might be bigger
    # linkCapacity *= 1000 # in kilobytes

    # Create a portal context.
    pc = portal.Context()

    # Create a Request object to start building the RSpec.
    #request = pc.makeRequestRSpec()
    request = pg.Request()

    # physical type of all nodes
    # Could choose which physical nodes are requested
    # As of now left for the resource mapper to decide
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
    # image with ovs-switch pre-installed, beware of Ubuntu version 18 instead of 20
    ovsImg = 'urn:publicid:IDN+emulab.net+image+emulab-ops:UBUNTU18OVS'

    # Add Switch to the request
    mysw = request.XenVM("switch")
    mysw.exclusive = True # otherwise overall bandwith is limited, and port for ssh connection would not be 22
    mysw.disk_image = img
    mysw.installRootKeys(True,True) # TODO: remove as it does not work

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
        node.installRootKeys(True,True) # TODO: remove this as it doesn't work
        
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
        link.link_multiplexing = True
        
    # receiver node
    rcvNode = request.RawPC("hdest")
    rcvNode.disk_image = img
    rcvNode.installRootKeys(True,True) # TODO: remove this as it doesn't work
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
    link.link_multiplexing = False
    
    # Print the RSpec to the enclosing page.
    return request.toXMLString(pretty_print=True, ucode=True)