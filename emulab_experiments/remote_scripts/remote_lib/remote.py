# Used for standard functions needed on all or multiple remote hosts

import os
import subprocess
import re
import yaml
import sys

def createFolderStructure(result_directory):
    '''
        Create folder structure for given path if directory path does not exist yet.
        Adds 'hostlogs/', 'hostdata/', 'condensed/' folders as leafs to the path

        Args:
            result_directory: folder path
    '''
    if not os.path.exists(result_directory):
        os.makedirs(result_directory)
    
    path = os.path.join(result_directory,'hostlogs')
    if not os.path.exists(path):
        os.makedirs(path)
    path = os.path.join(result_directory,'hostdata')
    if not os.path.exists(path):
        os.makedirs(path)
    path = os.path.join(result_directory,'condensed')
    if not os.path.exists(path):
        os.makedirs(path)
    path = os.path.join(result_directory,'queue')
    if not os.path.exists(path):
        os.makedirs(path)

def getSenderID():
    '''
        Gets sender id of any sender host (starting from 0) 

        Returns:
            (hostname, id) pair, hostname is the full name of the remote computer
        
        Raises:
            subprocess.CalledProcessError

    '''
    output = subprocess.check_output(["hostname"]).decode("utf-8")
    pattern = re.compile("[0-9]+")
    behavior_index = int(pattern.findall(output)[0])

    return output, behavior_index
        
def getConfig():
    '''
        Returns the config that is currently saved at this node from location '/local/config.yaml'

        Returns:
            config, a dictionary-like object of the experiment configuration
    '''
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()
    return config

# TODO: to be implemented
def getIface():
    '''
        Get network interface name connected to experiment network, only use this function
        for sender and receiver node. Will return 'unknown' at switch 
    '''
    return "iface"

def getName():
    '''
        Get hostname of host. e.g. sender2, switch or receiver
    '''
    output = subprocess.check_output(["hostname"]).decode("utf-8")
    output = output.split(".")
    return output[0]

def getDeviceNumber():
    '''
        Get an index number for this host.
        For sender this is between 1 and #sender.
        For receiver this is #sender + 1.
        For switch it returns 0 since it should not be used at switch

        Return:
            Integer of device number
    '''
    config = getConfig()
    numSender = int(config["senders"])
    name = getName()

    if name == "switch":
        return 0
    elif name == "receiver":
        return numSender+1
    elif "sender" in name:
        match = int(re.findall(r'\d+',name)[0])
        return match + 1
    else:
        # should never occur
        return -1

def measuredOnIndex():
    name = getName()
    if name == "receiver":
        return "Dest"
    else:
        return str(getDeviceNumber())


def ifaceNumberToDeviceNumber(ifaceNumber:int):
    '''
        Get last number of interface number. e.g. 10.0.0.x
        10.0.0.2 -> receiver
        10.0.0.x -> (x>2) senderY (Y == x-2)
    '''
    config = getConfig()
    numSender = int(config["senders"])
    if ifaceNumber == 2:
        return numSender + 1
    elif ifaceNumber == 1:
        return -1
    else:
        return ifaceNumber - 2


if __name__ == "__main__":
    # for testing purposes
    pass