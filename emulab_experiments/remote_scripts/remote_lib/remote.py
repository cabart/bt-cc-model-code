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
    output = subprocess.check_output(["hostname"]).decode("utf-8")
    output = output.split(".")
    return output[0]
