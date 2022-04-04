# Used for standard functions needed on all or multiple remote hosts

import os
import subprocess
import re
import yaml
import sys
import logging

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
    try:
        f = open("/local/config.yaml", "r")
        config = yaml.safe_load(f)
        f.close()
        return config
    except:
        raise Exception("No config file available")

# TODO: to be implemented
def getIface():
    '''
        Get network interface name connected to experiment network, only use this function
        for sender and receiver node. Will return 'unknown' at switch 
    '''
    return "iface"

def getName():
    '''
        Get hostname of host. e.g. h2, switch or hdest
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
    elif name == "hdest":
        return numSender+1
    elif "h" in name:
        match = int(re.findall(r'\d+',name)[0])
        return match
    else:
        # should never occur
        return -1

def measuredOnIndex():
    name = getName()
    if name == "hdest":
        return "Dest"
    else:
        return str(getDeviceNumber())


def ifaceNumberToDeviceNumber(ifaceNumber,numSenders):
    '''
        Get last number of interface number. e.g. 10.0.0.x
        10.0.0.2 -> hdest
        10.0.0.x -> (x>2) hY (Y == x-2)

        Args:
            ifaceNumber: should be an integer or string which can be converted to an integer
    '''
    if isinstance(ifaceNumber,str):
        ifaceNumber = int(ifaceNumber)
    elif not isinstance(ifaceNumber,int):
        raise Exception("Should be either string or int")

    #config = getConfig() # this is extremely slow, need to open file each time
    #numSender = int(config["senders"])
    if ifaceNumber == 2:
        return numSenders + 1
    elif ifaceNumber == 1:
        return -1
    else:
        return ifaceNumber - 2


def getLogger(logger_name:str):
    level = logging.DEBUG
    name = getName()
    try:
        config = getConfig()
        res_folder = os.path.join("/local/",config['result_dir'])
        createFolderStructure(res_folder)
        log_path = os.path.join(res_folder,"hostlogs/" + name + ".log")
    except Exception as e:
        log_path = "/local/node.log"
    
    f = open(log_path,"a")
    f.write("started logger: " + logger_name)
    f.close()

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    formatter = logging.Formatter('%(asctime)s:: %(levelname)s:: %(name)s:: %(message)s',datefmt="%H:%M:%S")

    fh = logging.FileHandler(log_path,mode="a")
    fh.setLevel(level)
    fh.setFormatter(formatter)

    logger.addHandler(fh)

    return logger


def getSenderIface(sender_name):
    '''
    To be implemented
    '''
    return

def getSenderIfaceAtSwitch(sender_name):
    '''
    To be implemented
    '''
    return

if __name__ == "__main__":
    # for testing purposes
    pass