#!/usr/bin/python3

# take tcpdump file and create condensed csv


#Debugging:
# sudo python3.5 logparser.py  results/25/2/200/100/cubic/TCP-1_STABLE-1/2020-05-01--15-54-30/

# sudo rm results/25/2/200/100/cubic/TCP-1_STABLE-1/2020-05-01--15-54-30/condensed/*

from datetime import datetime, timezone
import os
import sys
import re
import subprocess
import math
import json
import pandas as pd
import matplotlib.pyplot as plt
import yaml
import numpy as np
from remote_lib import remote
#from mininet_experiments.plotting import *
#from mininet_experiments.plotting_single import *
#from plotting import *
#from plotting_single import *


import pprint

# Notes:
# Now the statistics are gathered when processing the raw data.
# So far, there is only cropping available after the raw data processing, which messes up the stats.
# TODO: Allow for cropping that is applied during raw data traversal.
# --> this will probably make the loadCondensedData obsolete, which I think is not problem,
#       since the processing times were never that long anyway that it would require an intermediate repr.

# Note:
# The statistics gathering is not separated into origin (which could be relevant for the host)
# there could be a benefit in restructuring that at some later point.

logfolder = 'hostlogs/'
datafolder = 'hostdata/'
condenseddatafolder = 'condensed/'

TIMEAGGREGATION = 1  # Resolution of timestamps,  '1' rounds to 10ths of seconds, '2' rounds to 100ths, etc.
SMOOTHING       = 1

RESULT_FILE_PREFIX = ''


MERGE_INTERVALS = [[1,10]]#, [2,10]]

ALL_FLOWS = ['10.0.0.%d' % i for i in range(1,10+1)]
PLOT_KEYS = ['10.0.0.1', 'x.1-10'] #, 'x.2-10']
PLOT_CWND_KEYS = ['10.0.0.1']

SUM        = 'SUM'
MAX        = 'MAX'
AVG        = 'AVG'
VAR        = 'VAR'


plt.rc('text', usetex=True)
plt.rc('font', family='serif')
plt.rcParams['text.latex.preamble'] = r'\usepackage{amsmath}' + '\n' + r'\usepackage{amssymb}'





#--------------------------------------------------------------------------------
# Parse and merge all tcpdump files
# Store in csv file.
# Fields: timestamp, measured-on, from, to, load, payload, udp, seqno, ackno

# TCPDump command: tcpdump -tt -i *interface* -n -e -v
# TCPDump examples, note that each packet has two lines.
#   1.: tcp ack
#   1591169992.383735 00:00:00:00:00:03 > 00:00:00:00:00:01, ethertype IPv4 (0x0800), length 66:
#       (tos 0x0, ttl 64, id 38676, offset 0, flags [DF], proto TCP (6), length 52)
#   *Newlne*10.0.0.3.5002 > 10.0.0.1.45687: Flags [.], cksum 0x142a (incorrect -> 0x17f2), ack 5793, win 1322,
#       options [nop,nop,TS val 2348940903 ecr 463900240], length 0

#   2.: tcp load
#   1591169992.384107 00:00:00:00:00:01 > 00:00:00:00:00:03, ethertype IPv4 (0x0800), length 1514:
#       (tos 0x0, ttl 64, id 41707, offset 0, flags [DF], proto TCP (6), length 1500)
#     *Newlne* 10.0.0.1.45687 > 10.0.0.3.5002: Flags [.], cksum 0x19d2 (incorrect -> 0x18d7), seq 225889:227337, ack 0, win 83,
#     options [nop,nop,TS val 463900259 ecr 2348940903], length 1448

#   3.: tcp load on receiver
#   1591170909.231527 00:00:00:00:00:01 > 00:00:00:00:00:03, ethertype IPv4 (0x0800), length 1514:
#   (tos 0x0, ttl 64, id 43218, offset 0, flags [DF], proto TCP (6), length 1500)
#     10.0.0.1.53723 > 10.0.0.3.5002: Flags [.], cksum 0x19d2 (incorrect -> 0x1d9f), seq 31857:33305, ack 1, win 83,
#     options [nop,nop,TS val 464817101 ecr 2349857745], length 1448

#   4.: tcp ack on receiver
#   1591170909.229867 00:00:00:00:00:03 > 00:00:00:00:00:02, ethertype IPv4 (0x0800), length 66:
#   (tos 0x0, ttl 64, id 38616, offset 0, flags [DF], proto TCP (6), length 52)
#     10.0.0.3.5002 > 10.0.0.2.42931: Flags [.], cksum 0x142b (incorrect -> 0xf1be), ack 43441, win 83,
#     options [nop,nop,TS val 1393565944 ecr 2522814530], length 0

#   5.: udp load
#       1591171072.412952 00:00:00:00:00:02 > 00:00:00:00:00:03, ethertype IPv4 (0x0800), length 1512:
#       (tos 0x0, ttl 64, id 4493, offset 0, flags [DF], proto UDP (17), length 1498)
#     10.0.0.2.49426 > 10.0.0.3.5003: UDP, length 1470

#   6. udp load on receiver
#      1591171072.346113 00:00:00:00:00:02 > 00:00:00:00:00:03, ethertype IPv4 (0x0800), length 1512:
#      (tos 0x0, ttl 64, id 3905, offset 0, flags [DF], proto UDP (17), length 1498)
#     10.0.0.2.49426 > 10.0.0.3.5003: UDP, length 1470

# Update: Extended TCPDump to also dump the first 78 bytes of the packet as hex.
# TCP Example:
# 1591624876.928245 00:00:00:00:00:01 > 00:00:00:00:00:02, ethertype IPv4 (0x0800), length 1514:
#   (tos 0x0, ttl 64, id 23761, offset 0, flags [DF], proto TCP (6), length 1500)
#     10.0.0.1.48571 > 10.0.0.2.5002: Flags [.], seq 4180415067:4180416515, ack 2499899782, win 83,
#     options [nop,nop,TS val 1333958879 ecr 1160376676], length 1448
# 	0x0000:  4500 05dc 5cd1 4000 4006 c448 0a00 0001
# 	0x0010:  0a00 0002 bdbb 138a f92c 125b 9501 7186
# 	0x0020:  8010 0053 19d1 0000 0101 080a 4f82 98df
# 	0x0030:  4529 f164 3637 3839 3031 3233 3435 3637
# UDP Example (counter marked with ** ** ) :
# 1591625197.068204 00:00:00:00:00:01 > 00:00:00:00:00:02, ethertype IPv4 (0x0800), length 1512:
#   (tos 0x0, ttl 64, id 27029, offset 0, flags [DF], proto UDP (17), length 1498)
#     10.0.0.1.46012 > 10.0.0.2.5003: UDP, length 1470
# 	0x0000:  4500 05da 6995 4000 4011 b77b 0a00 0001
# 	0x0010:  0a00 0002 b3bc 138b 05c6 19da **0000 0005** <--- UDP Counter
# 	0x0020:  5ede 45ed 0001 0a58 0000 0000 0000 0000
# 	0x0030:  3031 3233 3435 3637 3839 3031 3233 3435

def parseTCPDumpMininet(datafiles, filedestination):
    print("datafiles:",datafiles)
    print("filedestination:",filedestination)
    # timestamp, measuredon, src, dest, load, payload, udpno, seqno, ackno
    more_output = True
    data = []
    data.append(['timestamp', 'measuredon', 'src', 'dest', 'load', 'payload', 'udpno', 'seqno', 'ackno', 'id'])
    for dfname in datafiles:

        measured_on = remote.measuredOnIndex()
        print(measured_on)
        datafile = RESULT_FILE_PREFIX+datafolder+dfname
        if more_output:
            print("Parsing datafile "+datafile+"...")

        wcOutput = str(subprocess.check_output(("wc -l "+datafile).split()))
        filelength = int(re.match(r'b\'(\d+).+', wcOutput).group(1))
        linecounter = 0

        with open(datafile, 'r') as df:
            linestring = '_'
            while(linestring):
                linestring = df.readline()
                linecounter += 1

                # Show progress
                if more_output:
                    if linecounter % 100000 == 0:
                        print("Read %d / %d lines." % (linecounter, filelength), end="\r")

                timestampMatcher = re.match(r'(\d+\.\d+).+\>.+', linestring)
                packetsizeMatcher = re.match(r'.+,\slength\s(\S+):.+', linestring)

                if (timestampMatcher and packetsizeMatcher): # If packet with timestamp and length:
                    try:
                        timestamp = timestampMatcher[1]
                        load = packetsizeMatcher[1]
                        id = int(re.match(r'.+,\sid\s(\d+).+', linestring).group(1))
                        offset = re.match(r'.+offset\s(\d+),.+', linestring)
                        if offset is None or int(offset.group(1)) != 0:
                            print("WARNING: Offset is not 0! ", linestring) # If this happens, it's a sign of fragmentation,
                                                                            # We should rethink the use of ID.
                        linestring = df.readline() # Proceed to second line of packet
                        linecounter += 1

                        hostOriginMatch = re.match(r'.*10\.0\.\d\.(\d+)\.\S+\s\>', linestring)
                        hostDestinationMatch = re.match(r'.+\>\s10\.0\.\d\.(\d+)\.\S+', linestring)
                        source = hostOriginMatch[1]
                        destination = hostDestinationMatch[1]
                        payload = int(re.match(r'.+,\slength\s(\S+)', linestring).group(1))

                        # Timeaggregation defines the granularity of the timestamps.
                        # timestamp = float(('%.'+str(TIMEAGGREGATION)+'f') % float(timestamp)) # Timestamp resolution
                        udpMatch = re.match(r'.+UDP.+', linestring)
                        sequenceMatch = re.match(r'.+seq\s(\d+):\d+.+', linestring) # Only capture right part of seqno range
                        # Assumption: only need right seqno. correct since iperf has consistent packet sizes.
                        #seqenceMatch = re.match(r'.+seq\s(\d+):(\d+).+', linestring)
                        ackedNrMatch = re.match(r'.+ack\s(\d+),.+', linestring)
                        if sequenceMatch:
                            seqno = int(sequenceMatch[1])
                        else:
                            seqno = -1
                        if ackedNrMatch:
                            ackno = ackedNrMatch[1]
                        else:
                            ackno = 0

                        # Parsing hexdump, depending if UDP or not
                        if udpMatch:
                            linestring = df.readline()
                            linestring = df.readline()  # Proceed to fourth line of packet
                            linecounter += 2
                            udpcMatch = re.match(r'\s*0x0010:\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\S+)\s+(\S+)', linestring)
                            udpno = int(udpcMatch[1] + udpcMatch[2], 16)
                        else:
                            udpno = -1
                        if sequenceMatch and udpMatch:
                            print("Sequence AND UDP. Weird!")

                        # change source and destination numbers from interface number to actual device number
                        print("iface source:",source,", type:",type(source))
                        print("iface destination:",destination,", type:",type(source))
                        source = remote.ifaceNumberToDeviceNumber(source)
                        destination = remote.ifaceNumberToDeviceNumber(destination)
                        print("correct source:",source,", type:",type(source))
                        print("correct destination",destination,", type:",type(destination))
                        line = [timestamp, measured_on, source, destination, load, payload, udpno, seqno, ackno, id]
                        data.append(line)
                    except:
                        if re.match(r'.+ICMP.+', linestring) is not None:  # ICMP is ok.
                            continue
                        else: # Else: Print
                            print("FAIL when parsing: ", linestring)
            print("Read all %d lines.                     " % (filelength))

        # Write compressed data to a csv file
        np.savetxt(filedestination, np.array(data), delimiter=",", fmt='%s')


#--------------------------------------------------------------------------------
# Get load data
def calculateLoad(econfig):
    hostname = remote.getName()

    parsed_data = RESULT_FILE_PREFIX + condenseddatafolder + 'tcpdump' + hostname + '.csv'
    if not os.path.exists(parsed_data):
        datafiles = [f for f in os.listdir(RESULT_FILE_PREFIX + datafolder)]
        parseTCPDumpMininet(datafiles, parsed_data)


def main():
    econfig = remote.getConfig()

    global RESULT_FILE_PREFIX
    RESULT_FILE_PREFIX = os.path.join("/local",econfig["result_dir"])

    econfig['more_output'] = False
    if not econfig['more_output']:
        import warnings
        warnings.simplefilter("ignore")

    print("============\nStarting with: ", RESULT_FILE_PREFIX, "\n==============")
    calculateLoad(econfig)
    #cwndData, ssthreshData = parseCwndFiles([f for f in os.listdir(RESULT_FILE_PREFIX+logfolder)])
    #if os.path.exists(RESULT_FILE_PREFIX+'bbr2_internals.log'):
    #    bbr2InternalsData = parse_bbr2_internals_file(RESULT_FILE_PREFIX+'bbr2_internals.log', RESULT_FILE_PREFIX+condenseddatafolder+'bbr2_internals.csv')


if __name__ == "__main__":
    main()