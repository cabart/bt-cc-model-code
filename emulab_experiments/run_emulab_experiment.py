"""Creates a network of n sender nodes, one receiver node and one virtual switch inbetween to connect them.

Instructions:
Click on any node in the topology and choose the `shell` menu item. When your shell window appears, use `ping` to test the link.

"""
#!/usr/bin/python3.8

# Heavily based on Simons code
# but aims for a clear distinction between config generation and experiment code

import sys
import yaml
import os
import time
import argparse
import random

from pexpect import pxssh
import subprocess

from generateRspec import *
from generateConfig import *
from serverCommunication import *
from emulabConnection import *

import logging
logging.basicConfig(format='%(asctime)s:: %(levelname)s:: %(message)s',datefmt="%H:%M:%S", level=logging.INFO)


def sourceLatency(nSender, minLat, maxLat):
    random.seed(1)
    lat = []
    for i in range(nSender):
        random_latency = int(random.uniform(minLat,maxLat)*10)/10
        lat.append(random_latency)
    return lat


def main(config_name, download):
    logging.debug("Setting up configuration")

    config = get_config(config_name)

    result_folder = 'results/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
        os.chown(result_folder, os.stat('.').st_uid, os.stat('.').st_gid)
    result_folder += config['name'] + '/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
        os.chown(result_folder, os.stat('.').st_uid, os.stat('.').st_gid)
    result_folder += 'emulab_experiments/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
        os.chown(result_folder, os.stat('.').st_uid, os.stat('.').st_gid)

    with open(config['emulab_parameters']['base_config'], 'r') as base_config_file:
        base_config = yaml.safe_load(base_config_file)

    logging.info("Number of combinations: " + str(len(config['param_combinations'])))

    # ------------------------
    # Do emulab setup for all experiments
    # ------------------------

    # get maximum values for senders and capacity
    maxSender = 0
    maxCapacity = 0
    for pc_map in config['param_combinations']:
        n = pc_map['senders']
        if n > maxSender:
            maxSender = n
        c = pc_map['link_capacity']
        if c > maxCapacity:
            maxCapacity = c
    logging.info("Max #sender in experiment: " + str(maxSender))
    logging.info("Max capacity in experiment: " + str(maxCapacity))

    # Create emulab connection object
    emulab_config = get_emulab_config("emulab_experiments/emulab_config.yaml")
    experiment_name = "emulab-experiment"
    try:
        emuServer = emulabConnection(emulab_config["username"],emulab_config["home"],emulab_config["certificate_location"],emulab_config["password_location"],experiment_name=experiment_name)
    except InitializeError as e:
        logging.error("Emulab initialization failed: " + str(e))
        logging.error("Connection could not get established, abort...")
        sys.exit(1)

    # generate rspec file
    rspec = createUnboundRspec(maxSender, maxCapacity)

    # start experiment hardware and wait until ready
    if emuServer.startExperiment(duration=1, rspec=rspec):
        logging.info("Experiment is ready\n")
    else:
        logging.info("Experiment is not ready, timeout maybe too low or there was an error when starting up")
        sys.exit(1)
    
    # Connect to all experiment nodes (sender, switch, receiver)
    connectAll = True
    sshKey = os.path.join(emulab_config["home"],emulab_config["ssh_key_location"])
    numSender = maxSender

    def connectSSH(nodename, port="22"):
        node = nodename + "." + experiment_name + ".emulab-net.emulab.net"
        s = pxssh.pxssh(options={"StrictHostKeyChecking": "no"},timeout=30)
        s.login(node,emulab_config["username"],port=port,ssh_key=sshKey,sync_multiplier=2)
        return s
    
    senderSSH = dict()
    for i in range(numSender):
        try:
            sender = "sender" + str(i)
            s = connectSSH(sender)
            senderSSH.update({sender: s})
        except pxssh.ExceptionPxssh as e:
            connectAll = False
            logging.error("Login to node failed: sender" + str(i))
            logging.error(e)

    # connect to receiver
    try:
        recSSH = connectSSH("receiver")
    except pxssh.ExceptionPxssh as e:
        connectAll = False
        logging.error("Login to receiver node failed: " + e)

    # connect to switch
    try:
        switchSSH = connectSSH("switch")
    except pxssh.ExceptionPxssh as e:
        connectAll = False
        logging.error("Login to switch node failed: " + e)

    # create a dictionary for all nodes
    allSSH = senderSSH.copy()
    allSSH.update({"receiver": recSSH, "switch": switchSSH})
    logging.debug("all ssh connections: " + str(allSSH))

    # all addresses for scp use
    allAddresses = dict()
    for k in allSSH.keys():
        address = emulab_config["username"] + "@" + k + "." + experiment_name + ".emulab-net.emulab.net"
        allAddresses.update({k:address})
    logging.debug("All addresses: " + str(allAddresses))

    # check all connections
    def uptimeCheckSSH(s:pxssh.pxssh):
        s.sendline("uptime")
        s.prompt()
        return str(s.before.decode("utf-8"))

    # Check if all connections worked and start experiment
    if connectAll:
        # do experiment
        for k,v in allSSH.items():
            logging.debug("Test " + k + " uptime: " + uptimeCheckSSH(v))
    else:
        logging.error("Some ssh connections did not work!")

    # ---------------
    # Start experiment with different parameter combinations
    # ---------------
    for pc_map in config['param_combinations']:
        # create configuration file for experiment
        exp_config = config_edited_copy(base_config, custom=pc_map)
        exp_config['base_res_dir'] = result_folder # same for all parameter configuration and runs

        # setup source latency ranges for this configuration
        senderLatencies = sourceLatency(exp_config['senders'],exp_config['source_latency_range'][0],exp_config['source_latency_range'][1])

        # Do all runs for a specific configuration
        for i in range(config['experiment_parameters']['runs']):
            # Do a single run of a parameter combination
            logging.info("Run " + str(i+1) + " / " + str(config['experiment_parameters']['runs']))
            exp_config = setup_configuration(exp_config, senderLatencies) # needs to be done every run

            # send config file to all nodes
            file = os.path.join(os.getcwd(),exp_config["result_dir"])
            file = os.path.join(file,"config.yaml")
            for k,v in allAddresses.items():
                retCode = subprocess.call(["scp","-P","22","-i",sshKey,file,v+":/local/config.yaml"])
                if retCode:
                    logging.error("Uploading of config file to " + k + " did not work")
                    sys.exit(1)
            logging.info("Experiment config successfully uploaded to every experiment node")
            
            logging.info("start measuring on switch, sender and receiver")
            # TODO: Start switch measurements
            #switchSSH.sendline("/local/bt-cc-model-code-main/switch/queueMeasurements.py")
            
            # Start 'receiver node' measurements
            recSSH.sendline("bash /local/bt-cc-model-code-main/receiver/receiving_host.sh")
            
            time.sleep(1) # make sure the server is running on receiver node
            # Start 'sender nodes' measurements
            for k,v in senderSSH.items():
                v.sendline("bash /local/bt-cc-model-code-main/sender/sending_host.sh")
            
            # receive answers
            for k,v in senderSSH.items():
                v.prompt()
                logging.info("started " + k + ": " + str(v.before.decode("utf-8")))

            recSSH.prompt()
            logging.info("started receiver: " + str(recSSH.before.decode("utf-8")))

            # end all tcpdump measurements
            for k,v in allSSH.items():
                logging.info("end tcpdump on " + k)
                v.sendline('sudo pkill -SIGTERM -f tcpdump')
                v.prompt()

            logging.info("Finished all measurements")

            if download:
                logging.info("start getting all measurement data from server")
                # TODO: get all data using scp
                for k,v in allAddresses.items():
                    source = v + ":" + os.path.join("/local/",exp_config["result_dir"])
                    target = os.path.join(os.getcwd(),exp_config["result_dir"])

                    retCode = subprocess.call(["scp","-rp","-P","22","-i",sshKey,source,target])
                    if retCode:
                        logging.error("Could not download results from " + k)
                logging.info("Download completed")
            else:
                logging.info("Set flag to not download files")


            for dir_name, _, file_names in os.walk(result_folder):
                for file_name in file_names:
                    os.chown(os.path.join(dir_name, file_name), os.stat('.').st_uid, os.stat('.').st_gid)

            
    # ---------------
    # Stop experiment and all connections
    # ---------------
    
    # logout from all ssh connections
    for k,v in allSSH.items():
        v.logout()

    # terminate experiment
    logging.info("All experiments done")
    while True:
        inp = input("Do you want to shutdown emulab hardware? [y/n]:") 
        if inp == "y" or inp == "yes" or inp == "Y" or input == "Yes":
            logging.info("Stop hardware")
            emuServer.stopExperiment()
            logging.info("Hardware has been stopped")
            break
        elif inp == "n" or inp == "no" or inp == "N" or inp == "No":
            logging.info("Do not stop hardware, may use up unneccessary hardware resources at emulab site")
            break
        else:
            logging.warn("invalid input")
    logging.info("All done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v","--verbosity",action="store_true",default=False,help="show debug output")
    parser.add_argument("-c","--config",type=str,default="./configs/test_config.yml", help="path to your config file")
    parser.add_argument("-d","--download",action="store_true",default=False,help="don't download results (for testing only)")
    args = parser.parse_args()

    if args.verbosity:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    if not os.path.exists(args.config):
        logging.info("File does not exist or path is wrong")
        sys.exit(1)
    else:
        main(args.config, not args.download)

