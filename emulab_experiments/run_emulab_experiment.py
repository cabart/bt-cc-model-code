"""Creates a network of n sender nodes, one receiver node and one virtual switch inbetween to connect them.

Instructions:
No instructions given since this rspec file is intended to be used for automated experiments using the emulab api.

"""
#!/usr/bin/python3.8

# loosely based on Simons code
# but aims for a clear distinction between config generation and experiment code

import sys
import yaml
import os
import time
import argparse
import random

from pexpect import pxssh
import subprocess

from create_rspec import *
from generate_config import *
from emulab_connection import *
from logparser import external_main as logparsermain

import logging
logging.basicConfig(format='%(asctime)s:: %(levelname)s:: %(message)s',datefmt="%H:%M:%S", level=logging.INFO)


def sourceLatency(nSender, minLat, maxLat):
    random.seed(1)
    lat = []
    for i in range(nSender):
        random_latency = int(random.uniform(minLat,maxLat)*10)/10
        lat.append(random_latency)
    return lat


def setupInterfaces(start,senderSSH,recSSH,switchSSH):
    logging.info("Setup interfaces")
    if start:
        flag = " -a"
        logging.info("Adding delay and capacity limits at all interfaces")
    else:
        flag = " -d"
        logging.info("Removing delay and capacity limits at all interfaces")
    
    for k,v in senderSSH.items():
        v.sendline("python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_setup_links.py" + flag)
        v.prompt()
    
    recSSH.sendline("python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/receiver_setup_links.py" + flag)
    recSSH.prompt()

    switchSSH.sendline("python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/switch_setup_links.py" + flag)
    switchSSH.prompt()
    logging.info("All interface setups done")


def disableIPv6(disable:bool,allSSH):
    if disable:
        logging.info("disable ipv6")
        val = "1"
    else:
        logging.info("enable ipv6")
        val = "0"
    
    for k,v in allSSH.items():
        logging.debug("disable/enable ipv6 on " + k)
        v.sendline('bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/node_disable_ipv6.sh ' + val)
        v.prompt()
        message = v.before.decode("utf-8")
        logging.debug("ipv6:" + str(message))


def addBBR(senderSSH):
    logging.info("enable bbr on all senders")
    for k,v in senderSSH.items():
        logging.debug("enable bbr on " + k)
        v.sendline('bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_add_bbr.sh')
        v.prompt()
        message = v.before.decode("utf-8")
    # only show output for last sender
    pattern = re.compile("net.ipv4.tcp_available_congestion_control = (.+)\r")
    matches = pattern.findall(message)[0].split()
    logging.info("supported CCAs on sender nodes: " + str(matches))


def downloadFiles(addresses,sshKey,remoteFolder,localFolder):
    for k,v in addresses.items():
        retCode = subprocess.call(["scp","-r","-P","22","-i",sshKey,v+":"+remoteFolder,localFolder])
        if retCode:
            logging.warning("downlaoding of config file from " + k + " did not work")
            sys.exit(1)


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
    # TODO: adapt experiment duration to number of configs and runs
    if emuServer.startExperiment(duration=4, rspec=rspec):
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

    # Add BBR support for all sender nodes
    addBBR(senderSSH)

    # Get information about hardware
    types = emuServer.getPCTypes()
    logging.info(str(types))

    # test unlimited bandwidth with one host
    logging.info("test theoretical bandwidth of connection")
    recSSH.sendline('sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/receiver_test_bandwidth.py')
    _,b = senderSSH[0]
    b.sendline('sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_test_bandwidth.py')
    logging.info("Test done")

    # ---------------
    # Start experiment with different parameter combinations
    # ---------------
    for pc_map in config['param_combinations']:
        # create configuration file for experiment
        exp_config = config_edited_copy(base_config, custom=pc_map)
        exp_config['base_res_dir'] = result_folder # same for all parameter configuration and runs

        # setup source latency ranges for this configuration
        senderLatencies = sourceLatency(exp_config['senders'],exp_config['source_latency_range'][0],exp_config['source_latency_range'][1])

        # TODO: test script on remote node first
        # enable/disable ipv6
        disableIPv6(exp_config["disable_ipv6"],allSSH)

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
        
            # Setup interfaces at senders, switch and receiver
            setupInterfaces(True,senderSSH,recSSH,switchSSH)
            
            logging.info("start measuring on switch, sender and receiver")

            # Start switch measurements
            switchSSH.sendline("nohup python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/switch_queue_measurements.py &")
            switchSSH.prompt()            
            response = switchSSH.before.decode("utf-8")

            pidPattern = re.compile("\[[0-9]+\] [0-9]+")
            number = re.compile("[0-9]+")

            extendedPid = pidPattern.findall(response)[0]
            pid_queue = number.findall(extendedPid)[1]
            logging.info("Started queue measurement with process id : " + pid_queue)
            
            # Start 'receiver node' measurements
            recSSH.sendline("bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/receiver_measurements.sh")
            
            time.sleep(1) # make sure the server is running on receiver node
            # Start 'sender nodes' measurements
            for k,v in senderSSH.items():
                v.sendline("bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_measurements.sh")
            
            # receive answers
            for k,v in senderSSH.items():
                v.prompt()
                logging.debug("started " + k + ": " + str(v.before.decode("utf-8")))

            recSSH.prompt()
            logging.debug("started receiver: " + str(recSSH.before.decode("utf-8")))

            # end all tcpdump measurements
            for k,v in allSSH.items():
                logging.info("end tcpdump on " + k)
                v.sendline('sudo pkill -SIGTERM -f tcpdump')
                v.prompt()
            
            switchSSH.sendline("sudo kill -SIGTERM " + pid_queue)
            switchSSH.prompt()
            logging.info("Stopped queue measurement: " + switchSSH.before.decode("utf-8"))

            logging.info("Finished all measurements")
            
            # remove interfaces at senders, switch, receiver
            # could be done only once for every parameter configuration, but we always
            # want fastest speeds possible for transferring data to receiver node
            setupInterfaces(False,senderSSH,recSSH,switchSSH)

            # create condensed tcpdump files on remote nodes
            logging.info("start creating condensed tcpdump files")
            for k,v in allSSH.items():
                if k == "switch": continue
                v.sendline("sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/remote_logparser.py")
                v.prompt()
                logging.info("created condensed tcpdump file on " + k)
            logging.info("finished all condensed remote tcpdump files")

            # download condensed folder files and queue measurements
            if download:
                logging.info("start getting all measurement data from server")
                baseRemoteFolder = os.path.join("/local",exp_config["result_dir"])
                baseLocalFolder = os.path.join(os.getcwd(),exp_config["result_dir"])

                # download condensed files
                remoteFolder = os.path.join(baseRemoteFolder,"condensed/")
                #localFolder = os.path.join(baseLocalFolder,"condensed/")
                downloadFiles(allAddresses,sshKey,remoteFolder,baseLocalFolder)

                # download logfiles
                remoteFolder = os.path.join(baseRemoteFolder,"hostlogs/")
                #localFolder = os.path.join(baseLocalFolder,"hostlogs/")
                downloadFiles(allAddresses,sshKey,remoteFolder,baseLocalFolder)

                # download queue measurements from switch
                remoteFolder = os.path.join(baseRemoteFolder,"queue/")
                #localFolder = os.path.join(baseLocalFolder,"queue/")
                downloadFiles(allAddresses,sshKey,remoteFolder,baseLocalFolder)

                logging.info("Download completed")

                logging.info("uncompress tcpdump files...")
                condensedFolder = os.path.join(baseLocalFolder,"condensed/")
                logging.info("condensedFolder: " + condensedFolder)
                cmd = "cat " + condensedFolder + "*.tar | sudo tar -xvf - -i --directory " + condensedFolder
                output = subprocess.check_output(cmd,shell=True,encoding="utf-8")
                logging.info("uncompressed: " + output)

                logging.info("remove compressed data")
                cmd = "find " + condensedFolder + "* -name '*.tar' -print | xargs sudo rm"
                output = subprocess.check_output(cmd,shell=True,encoding="utf-8")
                logging.info("removing of compressed files: " + output)

                logging.info("Find results of this run in: " + baseLocalFolder)
                
                logging.info("start local logparser")
                logparsermain(exp_config["result_dir"])
                logging.info("logparser finished")

                logging.info("remove condensed data files")
                cmd = "find " + condensedFolder + "* -name '*.csv' -print | xargs sudo rm"
                output = subprocess.check_output(cmd,shell=True,encoding="utf-8")
                logging.info("removed condensed data files: " + output)
            else:
                logging.info("Set flag to not download files")

            for dir_name, _, file_names in os.walk(result_folder):
                for file_name in file_names:
                    os.chown(os.path.join(dir_name, file_name), os.stat('.').st_uid, os.stat('.').st_gid)
                
        logging.info("All runs completed")

    logging.info("All parameter configurations done")
            
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
            logging.warning("invalid input")
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

