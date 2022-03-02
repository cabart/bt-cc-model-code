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

from generateRspec import *
from generateConfig import *
from serverCommunication import *
from emulabConnection import *

import logging
logging.basicConfig(format='%(asctime)s:: %(levelname)s:: %(message)s',datefmt="%H:%M:%S", level=logging.DEBUG)




def main(config_name):

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
    print("Number of combinations:",len(config['param_combinations']))
    first = True
    for pc_map in config['param_combinations']:
        # create configuration file for experiment
        exp_config = config_edited_copy(base_config, custom=pc_map)
        exp_config = setup_configuration(exp_config)

        #print(exp_config)
        if first:
            first = False
            # do experiment

            emulab_config = get_emulab_config("emulab_experiments/emulab_config.yaml")
            experiment_name = "emulab-experiment"
            try:
                emuServer = emulabConnection(emulab_config["username"],emulab_config["home"],emulab_config["certificate_location"],emulab_config["password_location"],experiment_name=experiment_name)
            except InitializeError as e:
                print("Emulab initialization failed:", str(e))
                print("Connection could not get established, abort...")
                sys.exit(1)

            print("Emulab server version:", emuServer.getVersion())
            

            # generate rspec file
            rspec = createUnboundRspec(exp_config)

            #if emuServer.startExperiment(duration=1, rspec=rspec):
            if emuServer.startExperiment(duration=1, rspec=rspec):
                print("Experiment is ready")
            else:
                print("Experiment is not ready, timeout maybe too low or there was an error when starting up")
                sys.exit(1)
            
            #vmPort = emuServer.getVMPorts()

            # Connect to all experiment nodes (sender, switch, receiver)
            connectAll = True
            sshPubKey = os.path.join(emulab_config["home"],emulab_config["ssh_key_location"])
            numSender = exp_config['inferred']['num_senders']

            def connectSSH(nodename, port="22"):
                node = nodename + "." + experiment_name + ".emulab-net.emulab.net"
                s = pxssh.pxssh(options={"StrictHostKeyChecking": "no"},timeout=30)
                s.login(node,emulab_config["username"],port=port,ssh_key=sshPubKey,sync_multiplier=2)
                return s
            
            senderSSH = []
            for i in range(numSender):
                try:
                    s = connectSSH("sender" + str(i))
                    senderSSH.append(s)
                    #node = "sender" + str(i) + "." + experiment_name + ".emulab-net.emulab.net"
                    #s = pxssh.pxssh(options={"StrictHostKeyChecking": "no"},timeout=30)
                    #s.login(node,emulab_config["username"],port="22",ssh_key=sshPubKey,sync_multiplier=2)
                    #senderSSH.append(s)
                except pxssh.ExceptionPxssh as e:
                    connectAll = False
                    logging.error("Login to node failed: sender" + str(i))
                    logging.error(e)
            
            if len(senderSSH) == numSender:
                logging.info("all sender logins worked")
            else:
                logging.error("some sender login connections failed")

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

            # check all connections
            def uptimeCheckSSH(s:pxssh.pxssh):
                s.sendline("uptime")
                s.prompt()
                return str(s.before.decode("utf-8"))

            # Check if all connections worked and start experiment
            if connectAll:
                # do experiment
                for i in range(numSender):
                    logging.debug("Test sender" + str(i) + " uptime:" + uptimeCheckSSH(senderSSH[i]))    
                logging.debug("Test switch uptime:" + uptimeCheckSSH(switchSSH))
                logging.debug("Test receiver uptime: " + uptimeCheckSSH(recSSH))

            else:
                logging.error("Some connections did not work!")

            # send config file to all sender and receiver
            for i in range(numSender):


            # logout from all ssh connections
            for i in range(numSender):
                senderSSH[i].logout()
            recSSH.logout()
            switchSSH.logout()

            # do experiment in between...
            exp_duration = 2
            print("Wait for " + str(exp_duration) + " minutes to shut down experiment")
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
        print("Please provide a multi-experiment config file.")
