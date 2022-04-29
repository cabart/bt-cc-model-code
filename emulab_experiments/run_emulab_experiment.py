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

# use a root logger
# change logging level by setting -v flag
import logging
logging.basicConfig(format='%(asctime)s:: %(levelname)s:: %(name)s:: %(message)s',datefmt="%H:%M:%S", level=logging.INFO)


class ExperimentConnections:
    
    senderSSH = None
    receiverSSH = None
    switchSSH = None
    loggedIn = False

    def __init__(self, ssh_key, num_sender, port, experiment_name, username):
        '''
            Used to connect to all experiment nodes using ssh. Does connect to
            to all Nodes when initiating. Use the logout() method before exiting
            the program.
        '''
        self.ssh_key = ssh_key
        self.num_sender = num_sender
        self.port = port
        self.experiment_name = experiment_name
        self.username = username
        self.connect()
    
    def connectSingle(self, nodename:str):
        '''
            Connect to single node to of experiment

            Args:
                nodename (str): Name of the node as stated in the rpsec file

            Returns:
                pxssh object with the ssh connection if connection did work,
                None otherwise
        '''
        try:
            node = f"{nodename}.{self.experiment_name}.emulab-net.emulab.net"
            s = pxssh.pxssh(options={"StrictHostKeyChecking": "no"},timeout=30)
            s.login(node,self.username,port=self.port,ssh_key=self.ssh_key,sync_multiplier=2)
            logging.debug(f"connect {node}:{s}")
            return s
        except pxssh.ExceptionPxssh as e:
            logging.warning(f"Could not establish ssh connection to {nodename}: {e}")
            return None

    def connect(self):
        '''
            Setup connection to all experiment nodes
        '''
        allConnected = True
        # connect to sender nodes
        self.senderSSH = dict()
        for i in range(1,self.num_sender+1):
            cur = f"h{i}"
            s = self.connectSingle(cur)
            if s is None: allConnected = False
            self.senderSSH.update({cur: s})

        self.receiverSSH = self.connectSingle("hdest")
        self.switchSSH = self.connectSingle("switch")

        self.loggedIn = True

        if (self.receiverSSH is None) or (self.switchSSH is None):
            allConnected = False
        
        return allConnected


    def logout(self):
        '''
            Logout ssh connctions to all experiment nodes
        '''
        for k,v in self.getAll().items():
            try:
                v.logout()
            except:
                logging.info(f"Could not log out of {k}")

        self.senderSSH = None
        self.receiverSSH = None
        self.switchSSH = None
        self.loggedIn = False

    def getAll(self):
        '''
            Get SSH connections to all experiment node as dictionary.
            The keys are the nodenames and the values a pxssh object
        '''
        if (self.senderSSH is not None) and (self.receiverSSH is not None) and (self.switchSSH is not None):
            allSSH = self.senderSSH.copy()
            allSSH.update({"hdest": self.receiverSSH, "switch": self.switchSSH})
            return allSSH
        else:
            logging.error("Some ssh connections do not exist, should connect first")

    def getSender(self):
        '''
            Get SSH connections to all experiment sender as dictionary.
            The keys are the nodenames and the values a pxssh object
        '''
        if self.senderSSH is None:
            logging.error("Sender ssh does not exist, should connect first")
        else:
            return self.senderSSH

    def getReceiver(self):
        ''' Get SSH connection to receiver node as pxssh object'''
        if self.receiverSSH is None:
            logging.error("Sender ssh does not exist, should connect first")
        else:
            return self.receiverSSH

    def getSwitch(self):
        ''' Get SSH connection to switch node as pxssh object'''
        if self.switchSSH is None:
            logging.error("Sender ssh does not exist, should connect first")
        else:
            return self.switchSSH
    
    def isLoggedIn(self):
        return self.loggedIn
    

def sourceLatency(nSender, minLat, maxLat):
    '''
        Generates pseude-random latencies for each sender.

        Args:
            nSender: Number of senders
            minLat: lowest latency limit
            maxLat: highest latency limit
        
        Returns:
            list of length nSender with pseudo-random latencies between minLat and maxLat
    '''
    random.seed(1)
    lat = []
    for _ in range(nSender):
        random_latency = int(random.uniform(minLat,maxLat)*10)/10
        lat.append(random_latency)
    logging.info("Sender latencies: " + str(lat))
    return lat


def setupInterfaces(start,sshConnections:ExperimentConnections):
    '''
        Setup all interfaces of experiment at senders, switch and receiver

        Args:
            start: Boolean whether setups are added or removed
        
        Returns:
            Nothing
    '''
    logging.info("Setup interfaces at all experiment nodes...")
    if start:
        flag = "-a"
        logging.info("Adding delay and capacity limits at all interfaces")
    else:
        flag = "-d"
        logging.info("Removing delay and capacity limits at all interfaces")
    
    for k,v in sshConnections.getSender().items():
        v.sendline(f"sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_setup_links.py {flag}")
        v.prompt()
        message = v.before.decode("utf-8")
        logging.info(f"{k}: {message}")
    
    sshConnections.getReceiver().sendline(f"sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/receiver_setup_links.py {flag}")
    sshConnections.getReceiver().prompt()

    sshConnections.getSwitch().sendline(f"sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/switch_setup_links.py {flag}")
    sshConnections.getSwitch().prompt()
    message = v.before.decode("utf-8")
    logging.info(f"switch setup: {message}")
    logging.info("All interface setups done.")


def disableIPv6(disable:bool,allSSH):
    '''
        Enable or disable IPv6 at all hosts
    '''
    if disable:
        logging.info("disable ipv6")
        val = "1"
    else:
        logging.info("enable ipv6")
        val = "0"
    
    for k,v in allSSH.items():
        logging.debug("disable/enable ipv6 on " + k)
        v.sendline(f"bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/node_disable_ipv6.sh {val}")
        v.prompt()
        message = v.before.decode("utf-8")
        logging.debug(f"ipv6: {message}")


def addBBR(allSender):
    '''
        Enable BBR on all sender nodes

        Args:
            sshConnections (ExperimentConnections)
    '''
    logging.info("Enable BBR on all senders")
    for k,v in allSender.items():
        logging.debug(f"Enable BBR on {k}")
        v.sendline('bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_add_bbr.sh')
        v.prompt()
        message = v.before.decode("utf-8")
    # only show output for last sender
    pattern = re.compile("net.ipv4.tcp_available_congestion_control = (.+)\r")
    matches = pattern.findall(message)[0].split()
    logging.info(f"Supported CCAs on sender nodes: {matches}")


def addBBR2(sshConnections:ExperimentConnections, emuServer:emulabConnection):
    '''
        Warning: Does not work consistently and may break experiment!
        Enable BBR2 on all sender nodes. Sender nodes are getting rebooted to complete
        installation. Liquorix kernel is being installed on all sender nodes.
        Wait for all ssh connections to reconnect, signaling a succuessful reboot before advancing.

        Args:
            sshConnections (ExperimentConnections)
    '''
    logging.info("Enable BBR2 on all senders...")
    for k,v in sshConnections.getSender().items():
        logging.info(f"Enable BBR2 on {k}")
        v.sendline('bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_add_bbr2.sh')
        #v.prompt()
        returnCodes = v.expect(["AllDoneBBR2"],timeout=240)
        logging.info(f"Return codes of BBR2 installation (should all be 0): {returnCodes}")
        message = v.before.decode("utf-8")
        logging.info(f"{k}: {message}")

    time.sleep(60)
    # Reboot all sender nodes
    for k,v in sshConnections.getSender().items():
        logging.info(f"Restart {k}")
        v.sendline('sudo reboot\n')

    # Wait for all senders to restart...
    logging.info("Wait until all sender pcs rebooted")

    time.sleep(30) # Wait to ensure reboot process is not aborted (very unlikely)
    sshConnections.logout()

    # Wait for host pcs to restart
    time.sleep(30)
    logging.info("Ignore all warnings that follow")
    logging.info("If reconnecting fails for more than a minute, something has likely gone wrong.")
    counter = 0
    while not sshConnections.connect():
        counter += 1
        logger.info("Reconnecting failed! Try again in 30 seconds")
        sshConnections.logout()
        time.sleep(30)
        if counter == 5:
            logging.error("Restart takes too long, abort experiment...")
            if emuServer.stopExperiment():
                logging.info("Stopped experiment hardware")
                sys.exit(1)
    logger.info("Reconnected to all host PCs!")

    logging.info("Check if BBR2 was installed successfully...")
    logging.info("If installed correct, BBR2 should be listed as an option:")
    for k,v in sshConnections.getSender().items():
        v.sendline('bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_get_congestion_protocols.sh')
        v.prompt()
        message = v.before.decode("utf-8")
        pattern = re.compile("net.ipv4.tcp_available_congestion_control = (.+)\r")
        matches = pattern.findall(message)[0].split()
        logging.info(f"Supported CCAs on sender node {k}: {matches}")
    logging.info("BBR2 setup done.")
    

def downloadFiles(addresses,sshKey,remoteFolder,localFolder):
    '''
        Download all files from remote server folder

        Args:
            addresses: Dictionary of remote pc addresses
            sshKey: location off sshkey file
            remoteFolder: folder on remote pc from which to download all files
            localFolder: folder on local pc where downloaded files should be placed into
    '''
    for k,v in addresses.items():
        retCode = subprocess.call(["scp","-r","-C","-P","22","-i",sshKey,v+":"+remoteFolder,localFolder])
        if retCode:
            logging.error(f"Downloading of file from {k} did not work ({remoteFolder})")


def checkUserInput(inp:str):
    '''
        Use this wrapper to get yes/no answers from user

        Args:
            inp: User input string 
        
        Returns:
            Returns a Boolean if yes or no was given.
            Otherwise returns a None object
    '''
    if inp == "y" or inp == "yes" or inp == "Y" or input == "Yes":
        return True
    elif inp == "n" or inp == "no" or inp == "N" or inp == "No":
        return False
    else:
        return None


def main(config_name, download, yesFlag, noexperimentFlag):
    '''
        Main function of experiment. Most important stuff happens here.

        Args:
            config_name: location of config file
            download (boolean): Defines if results should be downloaded to local pc.
                Don't download results to solve time when debugging
            yesFlag (boolean): Automatically start and stop experiment without further
                user input
            noexperimentFlag (boolean): Skip the experiment measurements. Use this for
                debugging, or to get emulab hardware for manual inspections or experiments
    '''
    logging.debug("Setting up configuration")

    config, bbr2 = get_config(config_name)

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

    # get emulab config
    emulab_config = get_emulab_config("emulab_experiments/emulab_config.yaml")
    experiment_name = "emulab-experiment"

    # ask user if config is correct
    logging.info("Experiment config:\n\tConfig name: {}\n\t#Combinations: {}\n\t#Senders (max): {}\n\t#bandwidth (max): {}\n\t#Runs per configuration: {}".format(
        config_name, str(len(config['param_combinations'])), str(maxSender), str(maxCapacity), str(config['experiment_parameters']['runs'])
        )
    )
    while not yesFlag:
        inp = input("Do you want to run this experiment config?\n [y/n]:") 
        ret = checkUserInput(inp)
        if ret is None:
            continue
        elif ret:
            logging.info("Start experiment...")
            break
        elif not ret:
            logging.info("Experiment is not being started")
            sys.exit(1)
        else:
            logging.warning("invalid input")

    # Create emulab connection object
    try:
        emuServer = emulabConnection(emulab_config["username"],emulab_config["home"],emulab_config["certificate_location"],emulab_config["password_location"],experiment_name=experiment_name)
    except InitializeError as e:
        logging.error("Emulab initialization failed: " + str(e))
        logging.error("Connection could not get established, abort...")
        sys.exit(1)

    # generate rspec file
    rspec = createUnboundRspec(maxSender, maxCapacity)

    # start experiment hardware and wait until ready
    if emuServer.startExperiment(duration=8, rspec=rspec):
        logging.info("Experiment is ready\n")
    else:
        logging.info("Experiment is not ready, timeout maybe too low or there was an error when starting up")
        sys.exit(1)
    
    # Connect to all experiment nodes (sender, switch, receiver)
    sshKey = os.path.join(emulab_config["home"],emulab_config["ssh_key_location"])
    numSender = maxSender

    # sshKey, numSender, port, experiment_name,username
    sshConnections = ExperimentConnections(sshKey,numSender,22,experiment_name,emulab_config["username"])

    # all node addresses for scp use
    allAddresses = dict()
    for k in sshConnections.getAll().keys():
        address = emulab_config["username"] + "@" + k + "." + experiment_name + ".emulab-net.emulab.net"
        allAddresses.update({k:address})
    logging.debug(f"All addresses: {allAddresses}")

    # check all connections, useful for debugging of ssh connections
    def uptimeCheckSSH(s:pxssh.pxssh):
        s.sendline("uptime")
        s.prompt()
        return str(s.before.decode("utf-8"))

    # Check if all connections worked and start experiment
    if sshConnections.isLoggedIn():
        # Check all connections by requesting their uptime
        for k,v in sshConnections.getAll().items():
            logging.debug(f"Test {k} uptime: {uptimeCheckSSH(v)}")
    else:
        logging.error("Some ssh connections did not work!")

    # Add BBR support for all sender nodes
    addBBR(sshConnections.getSender())

    # Add BBR2 support for all sender nodes if used in a experiment configuration
    if bbr2 and (not noexperimentFlag):
        addBBR2(sshConnections, emuServer)

    # Get information about hardware
    types = emuServer.getPCTypes()
    logging.info('used pc types in this experiment' + str(types))

    # test unlimited bandwidth with one host
    logging.info("test theoretical bandwidth of connection...")
    sshConnections.getReceiver().sendline('sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/receiver_test_bandwidth.py')
    time.sleep(2)
    someSender = list(sshConnections.getSender().items())[0][1]
    someSender.sendline('sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_test_bandwidth.py')
    sshConnections.getReceiver().prompt()
    someSender.prompt()
    logging.info("Test done")
    bandwidth = someSender.before.decode('utf-8')
    try:
        bandwidth = re.findall(r'bandwidth: (\d+)',bandwidth)[0] + " Mbit/s"
        logging.info("Max bandwidth with one sender with this setup: " + bandwidth)
    except:
        logging.warning("bandwidth test failed: " + bandwidth)

    # ---------------
    # Start experiment with different parameter combinations
    # ---------------
    if not noexperimentFlag:
        for pc_map in config['param_combinations']:
            # create configuration file for experiment
            exp_config = config_edited_copy(base_config, custom=pc_map)
            exp_config['base_res_dir'] = result_folder # same for all parameter configuration and runs

            # setup source latency ranges for this configuration
            senderLatencies = sourceLatency(exp_config['senders'],exp_config['source_latency_range'][0],exp_config['source_latency_range'][1])

            # enable/disable ipv6
            disableIPv6(exp_config["disable_ipv6"],sshConnections.getAll())

            # Do all runs for a specific configuration
            for i in range(config['experiment_parameters']['runs']):
                # Do a single run of a parameter combination
                logging.info("Run " + str(i+1) + " / " + str(config['experiment_parameters']['runs']))
                exp_config = setup_configuration(exp_config, senderLatencies) # needs to be done every run

                # send config file to all nodes
                file = os.path.join(os.getcwd(),exp_config["result_dir"])
                file = os.path.join(file,"config.yaml")
                for k,v in allAddresses.items():
                    retCode = subprocess.call(["scp","-C","-P","22","-i",sshKey,file,v+":/local/config.yaml"])
                    if retCode:
                        logging.error("Uploading of config file to " + k + " did not work")
                        sys.exit(1)
                logging.info("Experiment config successfully uploaded to every experiment node")
            
                # Setup interfaces at senders, switch and receiver
                setupInterfaces(True,sshConnections)
                
                logging.info("start measuring on switch, sender and receiver")

                # Start switch measurements
                sshConnections.getSwitch().sendline("sudo nohup python3 /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/switch_queue_measurements.py &")
                sshConnections.getSwitch().prompt()            
                response = sshConnections.getSwitch().before.decode("utf-8")
                try:
                    pid_queue = re.findall(r'\[\d+\] (\d+)',response)[0]
                except:
                    pid_queue = ""
                    logging.error("Got no process id: {}".format(response))

                logging.info("Started queue measurement")
                logging.info("Process id of queue measurement: {}".format(pid_queue))
                
                # Start 'receiver node' measurements
                logging.info("Start sender and receiver measurements")
                sshConnections.getReceiver().sendline("bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/receiver_measurements.sh")
                
                time.sleep(1) # make sure the server is running on receiver node
                # Start 'sender nodes' measurements
                for k,v in sshConnections.getSender().items():
                    v.sendline("bash /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/sender_measurements.sh")
                
                logging.info("Wait for at least {} seconds for measurements to complete".format(exp_config["send_duration"]))
                
                # receive answers
                for k,v in sshConnections.getSender().items():
                    v.prompt()
                    logging.info("started " + k + ": " + str(v.before.decode("utf-8")))

                sshConnections.getReceiver().prompt()
                logging.info("started receiver: " + str(sshConnections.getReceiver().before.decode("utf-8")))

                # end all tcpdump measurements
                for k,v in sshConnections.getAll().items():
                    logging.info("end tcpdump on " + k)
                    v.sendline('sudo pkill -SIGTERM -f tcpdump')
                    v.prompt()
                
                sshConnections.getSwitch().sendline("sudo kill -SIGTERM " + pid_queue)
                sshConnections.getSwitch().prompt()
                logging.info("Stopped queue measurement: " + sshConnections.getSwitch().before.decode("utf-8"))

                logging.info("Finished all measurements")
                
                # remove interfaces at senders, switch, receiver
                # could be done only once for every parameter configuration
                setupInterfaces(False,sshConnections)

                # create condensed tcpdump files on remote nodes
                # TODO: Could be done in parallel
                logging.info("start creating condensed tcpdump files")
                for k,v in sshConnections.getAll().items():
                    if k == "switch": continue
                    v.sendline("sudo python /local/bt-cc-model-code-main/emulab_experiments/remote_scripts/remote_logparser.py")
                    # This timeout is being ignored!
                    v.prompt(timeout=240) # add timeout since remote_logparser might take some time to complete
                    logging.info("created condensed tcpdump file on " + k)
                
                logging.info("finished all condensed remote tcpdump files")
                # This timer should be increased for larger measurements
                time.sleep(60)

                # download condensed folder files and queue measurements
                if download:
                    logging.info("start getting all measurement data from server")
                    baseRemoteFolder = os.path.join("/local",exp_config["result_dir"])
                    baseLocalFolder = os.path.join(os.getcwd(),exp_config["result_dir"])

                    # download condensed files
                    remoteFolder = os.path.join(baseRemoteFolder,"condensed/")
                    downloadFiles(allAddresses,sshKey,remoteFolder,baseLocalFolder)

                    # download logfiles
                    remoteFolder = os.path.join(baseRemoteFolder,"hostlogs/")
                    downloadFiles(allAddresses,sshKey,remoteFolder,baseLocalFolder)

                    # download queue measurements from switch
                    remoteFolder = os.path.join(baseRemoteFolder,"queue/")
                    downloadFiles(allAddresses,sshKey,remoteFolder,baseLocalFolder)

                    logging.info("Download completed")
                    logging.info(f"Find results of this run in: {baseLocalFolder}")
                    
                    logging.info("start local logparser")
                    logparsermain(exp_config["result_dir"])
                    logging.info("logparser finished")

                    logging.info("remove condensed data files")
                    condensedFolder = os.path.join(baseLocalFolder,"condensed/")
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
    else:
        logging.info("No experiment flag set")
            
    # ---------------
    # Stop experiment and all connections
    # ---------------
    
    # logout from all ssh connections
    sshConnections.logout()

    # terminate experiment
    logging.info("All experiments done")
    while True:
        if not yesFlag:
            inp = input("Do you want to shutdown emulab hardware? [y/n]:")
            ret = checkUserInput(inp)
        else:
            ret = checkUserInput("y")
        if ret is None:
            logging.warning("invalid input")
            continue
        elif ret:
            logging.info("Stop hardware")
            emuServer.stopExperiment()
            logging.info("Hardware has been stopped")
            break
        elif not ret:
            logging.info("Do not stop hardware, may use up unneccessary hardware resources at emulab site")
            break
    logging.info("All done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v","--verbosity",action="store_true",default=False,help="show debug output")
    parser.add_argument("-c","--config",type=str,default="./configs/test_config.yml", help="path to your config file")
    parser.add_argument("-d","--download",action="store_true",default=False,help="don't download results (for testing only)")
    parser.add_argument("-y","--yes",action="store_true",default=False,help="start and stop hardware automatically without asking")
    parser.add_argument("-n","--noexperiment",action="store_true",default=False,help="only start and stop hardware without actually doing experiment")
    args = parser.parse_args()

    if args.verbosity:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    if not os.path.exists(args.config):
        logging.info("File does not exist or path is wrong")
        sys.exit(1)
    else:
        main(args.config, not args.download, args.yes, args.noexperiment)

