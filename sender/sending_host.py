#!/usr/bin/python3

# Takes 3 arguments:
# hostID: provide an integer X, assuming the sending hostnames are 'hX'
# destHostID: provide the desthostID
# configloc: the location of the configfile (default file won't work. some by cc-experiment inferred values are needed)

import os
import sys
import subprocess
import re
import time
import random
import yaml
#from pyroute2 import IPRoute

INTERVALS = 15
PROBING_INTERVAL = 1

NPATHS = 1

INTERFACE = ''

import logging

logging.basicConfig(
    filename="/local/sender.log",
    format='%(asctime)s:: %(levelname)s:: %(message)s',
    datefmt="%H:%M:%S", 
    level=logging.DEBUG
)


def getInterface(): 
    output = subprocess.check_output(["ip","route","show","10.0.0.0/24"]).decode("utf-8")
    pattern = re.compile('dev \S*')
    logging.debug("Get all interfaces: " + str(pattern.findall(output)))
    result = str(pattern.findall(output)[0].split()[1])
    logging.info("interface: " + result)
    return result


# TODO: change interface to correct one
def startTcpDump(hostID):
    return
    for i in range(1):
        with open(config['result_dir']+'hostdata/'+str(hostID)+'-eth'+str(i)+'.log', 'w+') as f:
            tcpDumpCommmand = ('tcpdump -tt -i '+str(hostID)+'-eth'+str(i)+' -n -e -v -S -x -s 96').split()
            subprocess.Popen(tcpDumpCommmand, stdout=f, stderr=f)
            logging.info("Started tcpdump.")


def setTSO(hostID, on_mode):
    global INTERFACE
    mode = "on" if on_mode else "off"
    for ifID in range(NPATHS):
        turnoffTSOCommand = ("ethtool -K %s tso %s" % (INTERFACE, mode)).split()
        output = str(subprocess.check_output(turnoffTSOCommand))
        logging.info("set TSO output:" + str(output))
    logging.info("TSO turned " + str(mode))

# TODO: change this
def announceYourself(hostID, desthostID):
    global INTERFACE
    for ifID in range(NPATHS):
        logging.info("Announce %s" % (INTERFACE))
        pingCommand = ("ping -c 3 -I %s 10.0.%d.%d" % (INTERFACE, ifID, desthostID)).split()
        subprocess.call(pingCommand)
        continue

# This will always be executed; regardless of 'protocol' config.
def iperf_command_base(currPath, desthostID, IPNum, duration, sampling_period, format):
    return ("iperf -c 10.0.%s.%d -B 10.0.%s.%s -t %d -i %s -e -f %s " % (currPath, desthostID, currPath, IPNum, duration, sampling_period, format)).split()

def tcp_command(cc_flavour, mss):
    return ("-p 5002 -Z %s -M %d " % (cc_flavour, mss)).split()


def tcp_command_paced(cc_flavour, mss, cbr_as_pps, cbr_rate):
    if cbr_as_pps:
        return ("-p 5002 -Z %s -M %d -b %spps" % (cc_flavour, mss, cbr_rate)).split()
    else:
        return ("-p 5002 -Z %s -M %d -b %sm" % (cc_flavour, mss, cbr_rate)).split()

#def useCSRCommand(currPath, hostID):
#    return ("iperf -c 10.0.%s.%d -p 5002 -B 10.0.%s.%s -t %d -w %sM " % (currPath, DESTHOSTID, currPath, hostID, IPERF_DURATION, CSR_RATE)).split()

def udp_stable_command(cbr_as_pps, cbr_rate):
    if cbr_as_pps:
        return ("-p 5003 -u -b %spps " % (cbr_rate)).split()
    else:
        return ("-p 5003 -u -b %sm " % (cbr_rate)).split()

def udp_oscillation_command(currPath, IPNum, desthostID):
    return ("./oscillating-flow.py %s %d %s" % (IPNum, desthostID, config['result_dir'])).split()


def run(behavior_index, desthostID, config):
    global INTERFACE
    INTERFACE = getInterface()

    print(config['sending_behavior'][behavior_index].keys())
    hostID, behavior = [(i, j) for i, j in config['sending_behavior'][behavior_index].items()][0]
    IPNum = behavior_index + 3 # TODO: Check this

    logging.info("Started sending log of sender" + str(behavior_index))
    logging.info(">> " + str(desthostID))
    announceYourself(hostID, desthostID)
    startTcpDump(hostID)
    random.seed(hostID) # what is this used for?
    behavior = config['sending_behavior'][behavior_index][hostID]
    logging.info("Sending behavior: " + str(behavior))
    logging.info("(Should be something like tcp or udp)") # TODO: remove this line later

    # If duel mode, might have to wait:
    # special delay for protocol duels. see config
    if config['inferred']['num_senders'] == 2 and behavior['protocol'] == config['goes_second'] and config['duel_delay'] != 0:
        time.sleep(config['duel_delay'])
    command = iperf_command_base(0, desthostID, IPNum, config['send_duration'], config['iperf_sampling_period'], config['iperf_outfile_format'])
    protocol = behavior['protocol']
    if 'tcp' in protocol:
        #reduceMTUCommand = ("ifconfig h%s-eth%d mtu 100" % (hostID, 0)).split()
        #subprocess.call(reduceMTUCommand)
        setTSO(hostID, behavior['tso_on'])
        if protocol == 'tcp-cubic':
            command += tcp_command('cubic', config['mss'])
        elif protocol == 'tcp-reno':
            command += tcp_command('reno', config['mss'])
        elif protocol == 'tcp-cubic-paced':
            command += tcp_command_paced('cubic', config['mss'], config['cbr_as_pss'], config['inferred']['cbr_rate'])
        elif protocol == 'tcp-bbr':
            command += tcp_command('bbr', config['mss'])
        elif protocol == 'tcp-bbr2':
            command += tcp_command('bbr2', config['mss'])
        elif protocol == 'tcp-bbrsimon':
            command += tcp_command('bbrsimon', config['mss'])
        elif protocol == 'tcp-bbr2simon':
            command += tcp_command('bbr2simon', config['mss'])
    elif 'udp' in protocol:
        if protocol == "udp-stable":
            command += udp_stable_command(config['cbr_as_pss'], config['inferred']['cbr_rate'])
        elif protocol == "udp-oscillation":
            command = udp_oscillation_command(0, hostID, desthostID)
        else:
            print("Undefined UDP behavior.")
            return

    currPath = '0'

    #iperfoutputfile = (config['result_dir'] + "hostlogs/" + config['iperf_outfile_client']).replace("$", str(IPNum))
    iperfoutputfile = ("results/senderlogs/" + config['iperf_outfile_client']).replace("$", str(IPNum))
    fout = open(iperfoutputfile, 'w')

    time.sleep(2)
    logging.info("Executing Command: " +  str(command))
    iperf_Process = subprocess.Popen(command, stdout=fout)
    cwind_period = float(config['cwind_sampling_period'])
    if 'tcp' in protocol:
        for i in range(int(config['send_duration'] / cwind_period)):
            time.sleep(cwind_period)
            ssOutput = str(subprocess.check_output('ss -ti'.split()))
            #logging.info(ssOutput)
            m = re.match(r'.*(cwnd:\d+).*', ssOutput)
            if m is not None:
                logging.info(m.group(1))
            if 'tcp-bbr' in protocol:
                m = re.match(r'.*bbr:\(bw:(\S+).bps.*mrtt:(\S+),pac.*(pacing_rate \S+).bps.*(delivery_rate \S+).bps.*', ssOutput)
                if m is not None:
                    logging.info('btl_bw {} | mrtt {} | {} | {}'.format(m.group(1), m.group(2), m.group(3), m.group(4)) )
    else:
        time.sleep(config['send_duration'])
    iperf_Process.communicate()
    fout.close()
    logging.info("Host %s finished experiment" % hostID)
    print("finished")

#def parseargs():
#    behavior_index = int(sys.argv[1])
#    desthostID = int(sys.argv[2])
#    configfile_location = sys.argv[3]
#    return behavior_index, desthostID, configfile_location

if __name__ == "__main__":
    #behavior_index, desthostID, configloc = parseargs()
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()

    # create result folders on node
    if not os.path.exists("/local/results/senderlogs"):
        os.makedirs("/local/results/senderlogs")

    behavior_index = 0
    try:
        output = subprocess.check_output(["hostname"]).decode("utf-8")
        pattern = re.compile("[0-9]+")
        behavior_index = int(pattern.findall(output)[0])
        logging.info("username: " + output + " and behaviour_index: " + str(behavior_index))
    except subprocess.CalledProcessError as e:
        logging.error("Could not get sender number: " + str(e))
        sys.exit(1)

    run(behavior_index, 2, config)

