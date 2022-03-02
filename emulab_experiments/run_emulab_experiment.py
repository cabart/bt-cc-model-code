"""Creates a network of n sender nodes, one receiver node and one virtual switch inbetween to connect them.

Instructions:
Click on any node in the topology and choose the `shell` menu item. When your shell window appears, use `ping` to test the link.

"""
#!/usr/bin/python3.8

# Heavily based on Simons code
# but aims for a clear distinction between config generation and experiment code

from enum import auto
import sys
import yaml
import os
import pprint
import time

from pexpect import pxssh
import subprocess

from generateRspec import *
from generateConfig import *
from serverCommunication import *
from emulabConnection import *

import logging
logging.basicConfig(format='%(asctime)s:: %(levelname)s:: %(message)s',datefmt="%H:%M:%S", level=logging.INFO)


def main(config_name):
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

    # for now, only run one parameter combination
    logging.info("Number of combinations: " + str(len(config['param_combinations'])))
    first = True
    for pc_map in config['param_combinations']:
        # create configuration file for experiment
        exp_config = config_edited_copy(base_config, custom=pc_map)
        exp_config = setup_configuration(exp_config)

        #print(exp_config)
        # Do a single run of a single configuration
        if first:
            first = False
            # do experiment

            emulab_config = get_emulab_config("emulab_experiments/emulab_config.yaml")
            experiment_name = "emulab-experiment"
            try:
                emuServer = emulabConnection(emulab_config["username"],emulab_config["home"],emulab_config["certificate_location"],emulab_config["password_location"],experiment_name=experiment_name)
            except InitializeError as e:
                logging.error("Emulab initialization failed: " + str(e))
                logging.error("Connection could not get established, abort...")
                sys.exit(1)

            logging.debug("Emulab server version:" + str(emuServer.getVersion()))

            # generate rspec file
            rspec = createUnboundRspec(exp_config)

            #if emuServer.startExperiment(duration=1, rspec=rspec):
            if emuServer.startExperiment(duration=1, rspec=rspec):
                logging.info("Experiment is ready\n")
            else:
                logging.info("Experiment is not ready, timeout maybe too low or there was an error when starting up")
                sys.exit(1)
            
            # Connect to all experiment nodes (sender, switch, receiver)
            connectAll = True
            sshKey = os.path.join(emulab_config["home"],emulab_config["ssh_key_location"])
            numSender = exp_config['inferred']['num_senders']

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

            # send config file to all nodes
            file = os.path.join(os.getcwd(),exp_config["result_dir"])
            file = os.path.join(file,"config.yaml")
            for k,v in allAddresses.items():
                retCode = subprocess.call(["scp","-P","22","-i",sshKey,file,v+":/local/config.yaml"])
                if retCode:
                    logging.error("Uploading of config file to " + k + " did not work")
                    sys.exit(1)
            logging.info("Experiment config successfully uploaded to every experiment node")
            
            # TODO: Start switch measurements
            
            # TODO: start receiving host measurements
            recSSH.sendline("python /local/bt-cc-model-code-main/receiver/receiving_host.py")
            
            time.sleep(1)
            # TODO: start sending hosts measurements
            for k,v in senderSSH.items():
                v.sendline("bash /local/bt-cc-model-code-main/sender/sending_host.sh")
            
            # receive answers
            for k,v in senderSSH.items():
                v.prompt()
                logging.info("started sender" + k + ": " + str(v.before.decode("utf-8")))

            recSSH.prompt()
            logging.info("started receiver: " + str(recSSH.before.decode("utf-8")))

            # logout from all ssh connections
            for k,v in allSSH.items():
                v.logout()

            # do experiment in between...
            exp_duration = 2
            logging.info("Wait for " + str(exp_duration) + " minutes to shut down experiment")
            time.sleep(exp_duration*60)

            emuServer.stopExperiment()

        else:
            continue


        #for i in range(config['experiment_parameters']['runs']):
        #    print("Run", i+1, "/", config['experiment_parameters']['runs'])
            #run_cc(exp_config, result_folder)
            #for dir_name, _, file_names in os.walk(result_folder):
            #    for file_name in file_names:
            #        os.chown(os.path.join(dir_name, file_name), os.stat('.').st_uid, os.stat('.').st_gid)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        logging.error("Please provide a multi-experiment config file.")
