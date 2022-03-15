# Used for standard functions needed on all or multiple remote hosts

import os
import subprocess
import re
import sys

def createFolderStructure(result_directory):
    '''
        Create folder structure for given path if directory path does not exist yet.
        Adds 'hostlogs/', 'hostdata/', 'condensed/' folders as leafs to the path
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
        