#!/usr/bin/python3

import sys
import time
import subprocess
import yaml
import os

RESULT_FILE_PREFIX = ''

import logging
logging.basicConfig(
    filename="/local/receiver.log",
    format='%(asctime)s:: %(levelname)s:: %(message)s',
    datefmt="%H:%M:%S", 
    level=logging.DEBUG
)


def startTcpDump():
    # > '+RESULT_FILE_PREFIX+'hostdata/hDest-eth'+str(i)+'.log
    for i in range(1):
        with open(RESULT_FILE_PREFIX+'hostdata/hDest-eth'+str(i)+'.log', 'w+') as f:
            tcpDumpCommmand = ('tcpdump -tt -i hDest-eth'+str(i)+' -e -v -n -S -x -s 96').split()
            subprocess.Popen(tcpDumpCommmand, stdout=f, stderr=f)
            logging.info("Started tcpdump.")


# Start iperf server with TCP on destination hosts
def startTcpServer(config):
    #resfile = config['result_dir'] + config['iperf_outfile_server_tcp']
    resfile = os.path.join("/local/results",config['iperf_outfile_server_tcp'])
    samplingperiod = config['iperf_sampling_period_server']
    fout = open(resfile, "w")
    tcpIperfCommand = ('iperf -s -p 5002 -e -i %d -t %d -f %s' % (samplingperiod, config['send_duration'] + 5, config['iperf_outfile_format'])).split()
    logging.info("Starting TCP Server.")
    logging.info("Command: " + str(tcpIperfCommand))
    proc = subprocess.Popen(tcpIperfCommand, stdout=fout)
    logging.info("saved results to: ")
    return proc, fout

# Start iperf server with UDP on destination hosts
def startUdpServer(config):
    #resfile = config['result_dir'] + config['iperf_outfile_server_udp']
    resfile = os.path.join("/local/results",config['iperf_outfile_server_tcp'])
    samplingperiod = config['iperf_sampling_period_server']
    fout = open(resfile, "w")
    udpIperfCommand = ('iperf -s -p 5003 -u -e -i %d -t %d -f %s' % (samplingperiod, config['send_duration'] + 10, config['iperf_outfile_format'])).split()
    logging.info("Starting UDP Server.")
    logging.info("Command: " + str(udpIperfCommand))

    proc = subprocess.Popen(udpIperfCommand, stdout=fout)
    return proc, fout


def main(config):
    global RESULT_FILE_PREFIX
    RESULT_FILE_PREFIX = config['result_dir']
    logging.info("Started receiver node")

    # Announce yourself
    #pingCommand = ("ping -c 3 -I %s-eth%d 10.0.%d.%d" % ("hDest", 0, 0, 1)).split()
    #subprocess.call(pingCommand)

    numSender = config['senders']
    for i in range(numSender):
        s = i + 3
        code = subprocess.call(["ping","-c","1","10.0.0." + str(s)])
        if code:
            logging.error("address 10.0.0." + str(s) + " not reachable")
        else:
            logging.info("address could be reached: 10.0.0." + str(s))

    use_tcp = False
    use_udp = False
    protocols = [[a['protocol'] for a in client.values()][0] for client in config['sending_behavior']]
    for prot in protocols:
        if "tcp" in prot:
            use_tcp = True
        if "udp" in prot:
            use_udp = True

    logging.info("Use TCP: " + str(use_tcp) + " | Use UDP: " + str(use_udp))
    startTcpDump()
    if use_tcp:
        tcp_proc, tcp_f = startTcpServer(config)
    if use_udp:
        udp_proc, udp_f = startUdpServer(config)

    if use_tcp:
        tcp_proc.communicate()
        tcp_f.close()
        logging.info("Finished TCP Server.")
    if use_udp:
        udp_proc.communicate()
        udp_f.close()
        logging.info("Finished UDP Server.")

    print("finished")


#def parseargs():
#    desthostID = int(sys.argv[1])
#    configfile_location = sys.argv[2]
#    return desthostID, configfile_location

if __name__ == "__main__":
#    desthostID, configloc = parseargs()
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()
    main(config)