#!/usr/bin/python3
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
from plotting import *
from plotting_single import *
#from plotting import *
#from plotting_single import *


import pprint

import logging
#logger = logging.getLogger().getChild("logparser")
logger = logging.getLogger("root.logparser")
logger.info("created logparser logger")

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
queuefolder = 'queue/'

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


def inflight_calc(data, econfig):
    data.loc[:, 'inflight_sum'] = 0
    data.loc[:, 'bytes_acked'] = 0
    num_senders = econfig['inferred']['num_senders']
    for s in range(num_senders):
        sender = s+1
        sender_data = data[data.measuredon == str(sender)]
        last_byte_sent = -1
        last_byte_acked = -1
        for r, row in sender_data.iterrows():
            if row['src'] != num_senders+1:
                last_byte_sent = row['seqno']
                data.at[r, 'inflight_sum'] = max(last_byte_sent + row['payload'] - last_byte_acked, 0) if last_byte_acked != -1 else 0
            else:
                data.at[r, 'bytes_acked'] = max(row['ackno'] - last_byte_acked, 0)
                last_byte_acked = row['ackno']

    logger.info("Calculated inflight.")


# INPUT:
# key is either 'udpno' or 'seqno'
# Note: seqno != -1 => udpno == -1 && udpno != -1 => seqno == -1
# Requirement: the data passed contains only entries with 'identificator'-value != -1
#   Therefore: can not be a mix between UDP and TCP
# Requirement: the data passed is outbound traffic from sender to destination.
#   Therefore: ACK loss and latency is not calculated.
# OUTPUT:
# Losses are registered at timestamp where lost packet was sent.
# Latency is registered at the sender timestamp.

def loss_calc(received, sent, key):
    more_output = False

    if received.shape[0] == 0 or sent.shape[0] == 0:
        return received, sent
    data = sent.append(received)
    data.sort_values(by=[key, 'timestamp'], inplace=True)
    #print("Concatenated and sorted: ")
    #print(data)

    # Only for Seqno: Find duplicate keys in sender, mark not-last ones as losses
    if key == 'seqno':
        data.loc[(data.measuredon != 'Dest') & ((data[(data.measuredon != 'Dest')]).duplicated(subset=key, keep='last')), 'loss'] = 1

        # Technically, there should not be duplicates on the receiver side, but for some reason this happens. Is it when the resending is due to timeout?
        # We will keep track of it as well.
        data.loc[(data.measuredon == 'Dest') & (data[(data.measuredon == 'Dest')].duplicated(subset=key, keep='last')), 'double_receive'] = 1
        data.loc[(data.measuredon == 'Dest') & (data[(data.measuredon == 'Dest')].duplicated(subset=key, keep='last')), 'loss'] = 1 # Only for avoidng

    # Safety Check: No duplicate keys left among sender or receiver
    #if ~data.duplicated(subset='udpno', keep=False):
    dest_has_dupl = data[(data.loss == 0) & (data.measuredon == 'Dest')].duplicated(subset=key, keep=False).any()
    sender_has_dupl = data[(data.loss == 0) & (data.measuredon != 'Dest')].duplicated(subset=key, keep=False).any()
    if dest_has_dupl or sender_has_dupl:
        print("Problem: Duplicates of ", key, " in dest/sender: " +  str(dest_has_dupl) + "/" + str(sender_has_dupl))
        num_dest_dupl = np.count_nonzero(data[(data.loss == 0) & (data.measuredon == 'Dest')].duplicated(subset=key, keep=False))
        num_src_dupl = np.count_nonzero(data[(data.loss == 0) & (data.measuredon != 'Dest')].duplicated(subset=key, keep=False))
        if num_dest_dupl == num_src_dupl:
            print("But numbers are identical, so it's prob. ok.")
        else:
            print("Nonzeros in dest: ", num_dest_dupl)
            print("Nonzeros in sender: ", num_src_dupl)
            print(data[(data.loss == 0) & (data.measuredon == 'Dest')].duplicated(subset=key, keep=False))
            print(data[(data.loss == 0) & (data.measuredon != 'Dest')].duplicated(subset=key, keep=False))
            raise Exception

    # Now all remaining duplicates that are loss == 0 are the sent-received pair, therefore acked.
    # Therefore: find nonacked pairs/nonduplicates and mark them as losses.
    # TODO: nuance, safety check: check for nonduplicates on receiver side.
    data.loc[((data.loss == 0) & ~(data[(data.loss == 0)].duplicated(subset=key, keep=False))), 'loss'] = 1

    # Safety check: All non-lost packets are acked, therefore shapex should be the same
    receiver_shape = data[(data.loss == 0) & (data.measuredon == 'Dest')].shape
    sender_shape = data[(data.loss == 0) & (data.measuredon != 'Dest')].shape

    if more_output:
        print("Shapes: ", receiver_shape, " and ", sender_shape)
    if receiver_shape[0] != sender_shape[0]:
        print("Non-lost samples on receiver and sender do not match! Sender: ", sender_shape[0], " receiver: ", receiver_shape[0])
        with pd.option_context('display.max_rows', None):  # more options can be specified also
            #print(data)
            raise Exception
    eq = data[(data.loss == 0) & (data.measuredon == 'Dest')][key].values == data[(data.loss == 0) & (data.measuredon != 'Dest')][key].values
    if not eq.all():
        print("Equal length but not equal! ", eq)
        raise Exception

    # Logic
    data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'num'] = 1
    data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'latency_sum'] = \
        data.loc[(data.loss == 0) & (data.measuredon == 'Dest'), 'timestamp'].values - \
        data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'timestamp'].values
    data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'jitter_sum'] = \
        np.abs(data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'latency_sum'].values - \
        data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'latency_sum'].shift(1).values)
    data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'jitter_sum_sq'] = \
            np.square(data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'jitter_sum'].values)

    #print(data.loc[(data.loss == 0) & (data.measuredon != 'Dest'), 'jitter_sum'])

    if key == 'seqno':
        data.loc[(data.measuredon == 'Dest') & (data[(data.measuredon == 'Dest')].duplicated(subset=key, keep='last')), 'loss'] = 0 # Only for avoidng

    return data[(data.measuredon == 'Dest')], data[(data.measuredon != 'Dest')]

# Columns: timestamp, measuredon, src, dest, load, payload, udpno, seqno, ackno
def processTCPDdata(filename, econfig, timestep=0.1):
    df = pd.read_csv(filename, dtype={'timestamp': np.float64, 'measuredon': 'str', 'src': np.int64,
                                      'dest': np.int64, 'load': np.int64, 'payload': np.int64,
                                      'udpno': np.int64, 'seqno': np.int64, 'ackno': np.int64, 'id': np.int64,
                                      'udpno': np.int64, 'seqno': np.int64, 'ackno': np.int64, 'id': np.int64,
                                      })
    num_senders = econfig['inferred']['num_senders']
    receiver_no = num_senders + 1 # Todo: it's weird that sometimes 'Dest' is used and sometimes IP '11'. standardize!

    inflight_calc(df, econfig)

    # For some reason, Pandas does not accept assignment among non-strict subsets, 
    # e.g., df[(df.updno != -1)] =  df[(df.updno != -1)] if df == df[(df.updno != -1)]
    # Hence, we add this filler_df, which is a weird fix, but it works
    filler_df = pd.DataFrame({'timestamp': [-1], 'measuredon': ['-1'], 'src': [-1],
                              'dest': [11], 'load': [0], 'payload': [0],
                              'udpno': [-1], 'seqno': [-1], 'ackno': [-1], 'id': [-1]})

    resampled = []
    for s in range(num_senders):

        sender = s + 1
        received_from_sender = df[(df.src == sender) & (df.dest == receiver_no) & (df.measuredon == 'Dest')]
        received_from_sender.loc[:, 'loss'] = 0  # Does not contribute to lossstat, but is used in loss_calc

        sent_by_sender = df[(df.measuredon == str(sender)) & (df.src == sender) & (df.dest == receiver_no)].copy()
        filler_df.loc[0, 'timestamp'] = sent_by_sender['timestamp'].iloc[0]
        sent_by_sender = sent_by_sender.append(filler_df)
        sent_by_sender.loc[:, 'loss'] = 0
        sent_by_sender.loc[:, 'num'] = 0
        sent_by_sender.loc[:, 'latency_sum'] = 0.0  # In the beginning, it is the packet latency. Only later it is summed up.
        sent_by_sender.loc[:, 'jitter_sum'] = 0.0 # In the beginning, it is the packet jitter. Only later it is summed up.
        sent_by_sender.loc[:, 'jitter_sum_sq'] = 0.0
        received_from_sender.loc[:, 'double_receive'] = 0
        if econfig['more_output']:
            print("Shape:", received_from_sender.shape, " ", sent_by_sender.shape)
        try:
            received_from_sender[(received_from_sender.seqno != -1)], sent_by_sender[(sent_by_sender.seqno != -1)] = \
                loss_calc(received_from_sender[(received_from_sender.seqno != -1)], sent_by_sender[(sent_by_sender.seqno != -1)], 'seqno')
            _, sent_by_sender[(sent_by_sender.udpno != -1)] = \
                loss_calc(received_from_sender[(received_from_sender.udpno != -1)], sent_by_sender[(sent_by_sender.udpno != -1)], 'udpno')

        except:
            print("Error calculating loss and latency.")
            raise Exception

        # Senderside contributes: loss, latency_sum, latency_contributor_count
        sent_by_sender = sent_by_sender.filter(items=['timestamp', 'load', 'loss', 'latency_sum', 'num', 'jitter_sum', 'jitter_sum_sq', 'inflight_sum'])
        sent_by_sender = sent_by_sender.rename(columns={'load': 'load_sent'})
        sent_by_sender.loc[:, 'timestamp'] = pd.to_datetime(sent_by_sender.loc[:, "timestamp"], unit='s') # Need datetimeformat for resampling
        sent_by_sender = sent_by_sender.set_index('timestamp').resample(str(1000 * timestep) + 'ms', label='right').sum()
        sent_by_sender = sent_by_sender.add_suffix('_' + str(sender))
        resampled.append(sent_by_sender)
        if econfig['more_output']:
            print("Loss + Lat  + Jitter worked fine.")

        # Receiverside contributes: load, payload, number of double received packets.
        received_from_sender = received_from_sender.filter(items=['timestamp', 'load', 'payload', 'double_receive'])
        received_from_sender['timestamp'] = pd.to_datetime(received_from_sender["timestamp"], unit='s') # Need datetimeformat for resampling
        received_from_sender = received_from_sender.set_index('timestamp').resample(str(1000*timestep) + 'ms', label='right').sum()
        received_from_sender = received_from_sender.add_suffix('_' + str(sender))  # To make it distinguishable in table
        resampled.append(received_from_sender)

        # Backflow
        received_by_sender = df[(df.src == receiver_no) & (df.dest == sender) & (df.measuredon == str(sender))]
        received_by_sender = received_by_sender.filter(items=['timestamp', 'bytes_acked'])
        received_by_sender['timestamp'] = pd.to_datetime(received_by_sender["timestamp"], unit='s') # Need datetimeformat for resampling
        received_by_sender = received_by_sender.set_index('timestamp').resample(str(1000*timestep) + 'ms', label='right').sum()
        received_by_sender = received_by_sender.add_suffix('_' + str(sender))  # To make it distinguishable in table
        resampled.append(received_by_sender)


    load_table = pd.concat(resampled, axis=1, join='outer')
    load_table = load_table.reset_index()

    # Store it in epochs (unix seconds)
    load_table['abs_ts'] = load_table['timestamp'].values.astype(np.int64) / 1e9
    if econfig['more_output']:
        print("Absts appearance: ")
        print(load_table['abs_ts'])
    load_table['timestamp'] = (load_table.timestamp - load_table.timestamp.loc[0])  # Convert absolute time to timediff
    load_table['timestamp'] = load_table.timestamp.dt.total_seconds() # Elapsed seconds since start of experiment
    #print(load_table)
    load_table = load_table.sort_values(by=['timestamp'])
    load_table = load_table.set_index('timestamp')
    return load_table

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
    # get datafiles tcpdumpsender1, tcpdumpsender2, ...
    logger.info("Parse tcpdump files to single tcpdump file")
    logger.info(f"files to be parsed: {datafiles}")

    realPaths = []
    for path in datafiles:
        realPaths.append(RESULT_FILE_PREFIX + condenseddatafolder + path)
    logger.info(f"full paths: {realPaths}")

    df = pd.concat(map(pd.read_csv,realPaths),ignore_index=True)
    df.sort_values("timestamp",ignore_index=True)
    df.to_csv(filedestination,index=False)
    logger.info("parsed all tcpdump files to one file")


#--------------------------------------------------------------------------------
# Parse raw load data files
def parseCwndFiles(datafiles):
    more_output = False
    logger.info(f"Parsing CWND. Files: {len(datafiles)}")

    cwndData = {}
    ssthreshData = {}

    for df in datafiles:

        #print("File: ", df)
        m = re.match(r'h(\d+).*', df)
        if not m:
            continue
        hostNr = m.group(1)
        ip = '10.0.0.'+hostNr

        datafile = RESULT_FILE_PREFIX+logfolder+df
        more_output = True
        if more_output:
            logger.info(f"Parsing datafile {datafile}...")

        cwndData[ip]     = {}
        ssthreshData[ip] = {}

        with open(datafile, 'r') as df:

            linestring = '_'
            while(linestring):
                linestring = df.readline()

                dataField = re.match(r'(\S+)::.*cwnd:(\d+)', linestring)

                if dataField:
                    timestamp = float(dataField.group(1))
                    length = int(dataField.group(2))
                    cwndData[ip][timestamp] = length
                    continue

                dataField = re.match(r'(\S+)::.*unacked:(\d+)', linestring)

                if dataField:
                    timestamp = float(dataField.group(1))
                    length = int(dataField.group(2))
                    ssthreshData[ip][timestamp] = length

    #print(cwndDatai + " und "+ ssthreshData)
    return cwndData, ssthreshData

# Assuming file structure (csv): unix-timestamp,packets-in-queue
def readQueueFile(datafile):
    logger.info("Parsing queuefile.")


    # headers = ['ts', 'queue']
    # dtypes = {'ts': 'str', 'queue': 'int'}
    # parse_dates = ['col1', 'col2']
    # df = pd.read_csv(datafile, header=None, names=headers, dtypes=dtypes, parse_dates=parse_dates)
    # ts_column = pd.to_datetime(df.values[:,0], unit='s').second
    # queue_column = df.values[:,1]
    # return ts_column, queue_column



    headers = ['ts', 'queue1', 'queue']
    dtypes = {'ts': np.float64, 'queue': np.int64}
    df = pd.read_csv(datafile, header=None, names=headers, dtype=dtypes)

   # print(df)
    ts_column = df['ts']
    queue_column = df['queue']
    return ts_column, queue_column


# Parse BBR2 internals file (only works if module bbr2simon with additional debug output is enabled)
def parse_bbr2_internals_file(log_file_name, output_file_name):

    with open(log_file_name, 'r') as log_file:

        timestamp_start = -1
    
        data = [['timestamp', 'sender_id', 'inflight_lo', 'inflight_hi', 'bdp']]
    
        linestring = '_'
        while (linestring):
            linestring = log_file.readline()
            m = re.match(r'(\S+)\sBBR\s\d+\.\d+\.\d+.(\d+).*il\s(\S+)\sih\s(\S+).*bdp\s(\S+).*', linestring)
            if m is not None:
    
                # Timestamp parsing (expects ISO timestamp of dmesg)
                timestamp_iso = m.group(1)
                timestamp_utc = datetime.strptime(timestamp_iso, '%Y-%m-%dT%H:%M:%S,%f%z')
                timestamp_unix = (timestamp_utc - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
                if timestamp_start < 0:
                    timestamp_start = timestamp_unix
                timestamp = timestamp_unix - timestamp_start
    
                # Value parsing
                sender_id = int(m.group(2))
                inflight_lo = int(m.group(3))
                inflight_hi = int(m.group(4))
                bdp = int(m.group(5))
    
                data.append( [timestamp, sender_id, inflight_lo, inflight_hi, bdp] )


    np.savetxt(output_file_name, np.array(data), delimiter=',', fmt='%s')

#--------------------------------------------------------------------------------
# Collect timestamps from load data
def collectTimestamps(data):

    timestamps = {}
    for path in data.keys():
        for origin in data[path].keys():
            for timestamp in data[path][origin].keys():
                timestamps[timestamp] = {}

    return list(timestamps.keys())


#--------------------------------------------------------------------------------
# Separate data into load and receive data
def separateData(data):
    recvData = {}
    sendData = {}
    dfileKeys = list(data.keys())
    for dfile in dfileKeys:
        if 'Dest' not in dfile: # It's one of the sending hosts
            hostNr = re.match(r'.*h(\d+)-.*', dfile).group(1)
            sendData = {**sendData, **data[dfile]} # Dumping all dictionaries into one
        else: # It's the destination host
            recvData = data[dfile]

    return recvData, sendData

#--------------------------------------------------------------------------------
# Calculate load statistics
def calculateLoadStat(data, timestamps, direction):
    allFlowsKey = 'x.1-10'
    loadStat = {}
    for origin in data.keys():
        print("Calc Load Stat: ", origin)
        flowLoadData          = [data[origin][ts] for ts in timestamps]
        loadStat[origin]      = {}
        loadStat[origin][SUM] = sum(flowLoadData)
        loadStat[origin][MAX] = max(flowLoadData)
        loadStat[origin][AVG] = loadStat[origin][SUM]/len(flowLoadData)
        loadStat[origin][VAR] = math.sqrt(1/len(flowLoadData) *\
                                sum([(fld-loadStat[origin][AVG])**2 for fld in flowLoadData]))

    with open(RESULT_FILE_PREFIX+direction+'Stat.json', 'w+') as loadStatFile:
        json.dump(loadStat, loadStatFile, sort_keys=True, indent=4)

    return loadStat


#--------------------------------------------------------------------------------
# Complete load data (no packets at a time result in a missing timestamp for an interface)
def fillinData(data, timestamps):

    for timestamp in timestamps:
        for origin in data.keys():
            try:
                data[origin][timestamp] += 0.0
            except KeyError:
                data[origin][timestamp] = 0.0

    return data


#--------------------------------------------------------------------------------
# Smooth load data (average)
def smoothData(data):

    smoothedData = {}
    for origin in data.keys():
        smoothedData[origin] = {}
        timestamps = list(data[origin].keys())
        for t in range(len(timestamps)):
            leftTimestamp  = max(t - SMOOTHING, 0)
            rightTimestamp = min(t + SMOOTHING, len(timestamps))
            relevantData = [data[origin][tt] for tt in timestamps[leftTimestamp:rightTimestamp]]
            smoothedData[origin][timestamps[t]] = sum(relevantData)/len(relevantData)

    return smoothedData


#--------------------------------------------------------------------------------
# Merge flow data (average)
def mergeFlows(data):
    mergeKeys  = ['x.%d-%d' % (MERGE_INTERVALS[i][0], MERGE_INTERVALS[i][1]) for i in range(len(MERGE_INTERVALS))]
    originalKeys = list(data.keys())
    for i in range(len(MERGE_INTERVALS)):
        mergeInterval = MERGE_INTERVALS[i]
        mergeKey = mergeKeys[i]
        data[mergeKey] = {}
        for origin in originalKeys:
            m = re.match(r'.+\.(\d+)$', origin)
            if not m:
                continue
            hostID = int(m.group(1))
            if hostID < mergeInterval[0] or hostID > mergeInterval[1]:
                continue
            for timestamp in data[origin].keys():
                relevantData = data[mergeKey]
                try:
                    relevantData[timestamp] += data[origin][timestamp]
                except KeyError:
                    relevantData[timestamp] = data[origin][timestamp]
    return data


# TODO sis redundant. will be calculated in plotting functions. however, some adaption needed in plotting before deletion
def calculateTotal(df, num_senders):
    df['total_load'] = (df[['load_' + str(i+1) for i in range(num_senders)]]).sum(axis=1)
    df['total_payload'] = (df[['payload_' + str(i+1) for i in range(num_senders)]]).sum(axis=1)
    return df
    #TODO df['total_latency']


#--------------------------------------------------------------------------------
# Get load data
def calculateLoad(econfig):

    parsed_data = RESULT_FILE_PREFIX + condenseddatafolder + 'tcpdump.csv'
    if not os.path.exists(parsed_data):
        # tcpdump.csv does not exist
        datafiles = [f for f in os.listdir(RESULT_FILE_PREFIX + condenseddatafolder)]
        parseTCPDumpMininet(datafiles, parsed_data)

    condensed_data_file = RESULT_FILE_PREFIX + condenseddatafolder + 'tcpd_dataframe.csv'

    if not os.path.exists(condensed_data_file):
        datatable = processTCPDdata(parsed_data, econfig, econfig['plot_load_resolution'])
        datatable = calculateTotal(datatable, econfig['inferred']['num_senders'])
        datatable.to_csv(condensed_data_file)
    else:
        print("Loading condensed: ", condensed_data_file)
        datatable = pd.read_csv(condensed_data_file, dtype=np.float64)
        datatable = datatable.set_index("timestamp")

    # Convert timestamps from datetime to elapsed time
    #print(datatable)

    # Truncate
    exp_duration = econfig['send_duration']
    # TODO: better to have actual last tcpdump measurement instead of exp_duration as last timestamp
    truncate_front = econfig['truncate_front']
    truncate_back = econfig['truncate_back']
    datatable = datatable.truncate(before=truncate_front, after=exp_duration - truncate_back)
    #print(datatable)
    #datatable.fillna(0)

    return datatable


# Adapted this technique from previous code. Not in use since the yaml config file system
def config_from_resfolderpath(resfolderpath):
    regex = r'results\/\d+\/(.+)\/(.+)\/(.+)\/(.+)\/(.+)\/.+'
    m = re.match(regex, resfolderpath)
    config = {}
    config['nSrcHosts'] = m.group(1)
    config['linkCap'] = m.group(2)
    config['bufferCap'] = m.group(3)
    config['ccFlavour'] = m.group(4)
    sendBehav = m.group(5)
    config['sendBehav'] = sendBehav.replace('_', ' ')
    return config

def loadExperimentConfig(resultpath):
    print(resultpath)
    f = open(resultpath + 'config.yaml')
    config = yaml.safe_load(f)
    f.close()
    return config


# Designed for load in MBytes, throughput in Mbits/sec and windows in K
def extract_iperf_tcp_client(filename):
    regex = r'\[\s+(\S+)\].+-(\S+)\s+sec\s+(\S+)\s+MBytes\s+(\S+)\s+MBytes/sec\s+(\d+)/(\d+)\s+(\d+)\s+(\d+)K/(\d+)\s+us.*'
    column_names = ['id', 'interval_end_time','transfer','bandwidth','write','err','retries','cwnd','rtt']
    return extract_data_regex(filename, column_names, regex)

def extract_iperf_udp_client(filename):
    column_names = ['id', 'interval_end_time','transfer','bandwidth','pps']
    regex = r'\[\s+(\S+)\].+-(\S+)\s+sec\s+(\S+)\s+MBytes\s+(\S+)\sMBytes/sec\s+(\d+)\spps.*'
    return extract_data_regex(filename, column_names, regex)

def extract_iperf_udp_server(filename):
    column_names = ['id', 'interval_end_time','transfer','bandwidth','jitter', 'lost', 'total', 'lossrate',
             'avg_lat', 'min_lat', 'max_lat', 'stdev_lat', 'pps']
    regex = r'\[\s+(\S+)\].+-(\S+)\s+sec\s+(\S+)\s+MBytes\s+(\S+)\s+MBytes/sec\s+(\S+)\sms\s+(\d+)/\s*(\d+)\s*\((\S+)%\)\s*(\S+)/\s*(\S+)/\s*(\S+)/\s*(\S+)\s+ms\s+(\d+)\spps.*'
    return extract_data_regex(filename, column_names, regex)

def extract_iperf_tcp_server(filename):
    column_names = ['id', 'interval_end_time', 'transfer', 'bandwidth', 'reads', 'reads_dist']
    regex = r'\[\s+(\S)\].+-(\S+)\s+sec\s+(\S+)\s+MBytes\s+(\S+)\s+MBytes/sec\s+(\d+)\s+(\S+:\S+).*'
    return extract_data_regex(filename, column_names, regex)

# Extract data from file
# designed to work for every kind of regex dataextraction
# Stores data in pandas dataframe. stored as strings
def extract_data_regex(filename, column_names, regex):
    print("Extracting from : ", filename)

    data = []
    with open(filename, 'r') as f:
        linestring = '0'
        while (linestring):
            linestring = f.readline()
            mobj = re.match(regex, linestring)
            if mobj is None:
               # print("Is none:", linestring)
                continue
            if len(mobj.groups()) != len(column_names):
                print("Mismatched for columnnames: ", column_names, ".\nLine:", linestring)
                continue
            #print("a", end="")
            sample = [mobj.groups()[i] for i in range(len(column_names))]
            data.append(sample)
    array = np.array(data)
    if data == []:
        print("No data available from: ", filename)
    else:
        print("Datashape of ", filename, ": ", array.shape)
    #print(array)
    return pd.DataFrame(array, columns=column_names, dtype="string")

def extractIperf(econfig):
    clients_data = []
    server_data = []
    protocols = [[a['protocol'] for a in client.values()][0] for client in econfig['sending_behavior']]
    for i in range(econfig['inferred']['num_senders']):
        iperfoutputfile = (RESULT_FILE_PREFIX + econfig['iperf_outfile_client']).replace("$", str(i+1))
        if 'tcp' in protocols[i]:
            clients_data.append(extract_iperf_tcp_client(iperfoutputfile))
        elif 'udp' in protocols[i]:
            clients_data.append(extract_iperf_udp_client(iperfoutputfile))
        else:
            print("ERROR: No parser for this protocol: ", protocols[i], ", file: ", iperfoutputfile)
    serverfile = RESULT_FILE_PREFIX + econfig['iperf_outfile_server_udp']
    if os.path.exists(serverfile):
        server_data.append(extract_iperf_udp_server(serverfile))
    serverfile = RESULT_FILE_PREFIX + econfig['iperf_outfile_server_tcp']
    if os.path.exists(serverfile):
        server_data.append(extract_iperf_tcp_server(serverfile))

    return clients_data, server_data



def loadFromCSV(filename):
    f = open(filename, 'r')
    df = pd.read_csv(f, header=None)
    return df

def main(savePlot=False):

    econfig = loadExperimentConfig(RESULT_FILE_PREFIX)
    econfig['more_output'] = False
    if not econfig['more_output']:
        import warnings
        warnings.simplefilter("ignore")

    logger.info("Starting with: {}".format(RESULT_FILE_PREFIX))
    tcpd_data = calculateLoad(econfig)
    cwndData, ssthreshData = parseCwndFiles([f for f in os.listdir(RESULT_FILE_PREFIX+logfolder)])
    #memdata = loadFromCSV(RESULT_FILE_PREFIX + "sysmemusage.csv")
    if os.path.exists(RESULT_FILE_PREFIX+'bbr2_internals.log'):
        bbr2InternalsData = parse_bbr2_internals_file(RESULT_FILE_PREFIX+'bbr2_internals.log', RESULT_FILE_PREFIX+condenseddatafolder+'bbr2_internals.csv')

    startTimestamp = tcpd_data.index.values[0]
    endTimestamp = tcpd_data.index.values[-1]

    startAbsTs = tcpd_data['abs_ts'].values[0]
    endAbsTs = tcpd_data['abs_ts'].values[-1]
    queueTs, queueVal = readQueueFile(RESULT_FILE_PREFIX + queuefolder + "queue_length.csv")
    logger.info("Start/End timestamp: {}, {}".format(startTimestamp,endTimestamp))
    num_axes = sum([econfig['plot_loss'], econfig['plot_throughput'], econfig['plot_jitter'],
                    econfig['plot_cwnd'], econfig['plot_latency'], econfig['plot_queue'], econfig['plot_memory'],
                   2 * econfig['plot_iperf_losslat']])

    plt.figure('overview', figsize=(2, 2 * num_axes))

    fig, axes = plt.subplots(nrows=num_axes, num='overview', ncols=1, sharex=True, figsize=(100,4))

    xticks = []
    stats = {}
    ax_indx = 0
    figurename = "overview"
    if econfig['plot_throughput']:
        stats.update(plotLoad(figurename, axes[ax_indx], tcpd_data, startTimestamp, endTimestamp, econfig))
        ax_indx += 1
    if econfig['plot_cwnd']:
        stats.update(plotCwnd(figurename, axes[ax_indx], cwndData, ssthreshData, startAbsTs, endAbsTs, xticks))
        ax_indx += 1

    if econfig['plot_queue']:
        bdp = econfig['inferred']['bw_delay_product']
        real_buffer_size = bdp + int(econfig['switch_buffer'] * bdp)
        stats.update(plotQueue(figurename, axes[ax_indx], queueTs, queueVal, startAbsTs, endAbsTs, econfig['inferred']['bw_delay_product'],
                               real_buffer_size , xticks, econfig))
        ax_indx += 1
    if econfig['plot_latency']:
        stats.update(plotLatency(figurename, axes[ax_indx], tcpd_data, startTimestamp, endTimestamp, econfig))
        ax_indx += 1
    if econfig['plot_jitter']:
        stats.update(plotJitter(figurename, axes[ax_indx], tcpd_data, startTimestamp, endTimestamp, econfig))
        ax_indx += 1
    if econfig['plot_loss']:
        stats.update(plotLoss(figurename, axes[ax_indx], tcpd_data, startTimestamp, endTimestamp, econfig))
        ax_indx += 1
    if econfig['plot_memory']:
        print("memory plotting not supported for emulab experiments")
        #stats.update(plotMemory(figurename, axes[ax_indx], memdata, startAbsTs, endAbsTs, econfig))
        ax_indx += 1

    # TODO: iperf not well tested
    if econfig['plot_iperf_losslat']:
        iperf_client_data, iperf_server_data = extractIperf(econfig)
        plotLatencyIperf(axes[ax_indx], iperf_client_data, iperf_server_data, econfig, xticks)
        ax_indx += 1
        plotLossIperf(axes[ax_indx],  iperf_client_data, iperf_server_data, econfig, xticks)

    # Single Plots With own function
    # plotLoadOwn(tcpd_data, startTimestamp, endTimestamp, econfig, RESULT_FILE_PREFIX + "throughput.png")
    # plotMemoryOwn(memdata, startAbsTs, endAbsTs, econfig, RESULT_FILE_PREFIX + "memory.png")
    # plotLossOwn(tcpd_data, startTimestamp, endTimestamp, econfig, RESULT_FILE_PREFIX + "loss.png")
    # plotJitterOwn(tcpd_data, startTimestamp, endTimestamp, econfig, RESULT_FILE_PREFIX + "jitter.png")
    # plotLatencyOwn(tcpd_data, startTimestamp, endTimestamp, econfig, RESULT_FILE_PREFIX + "latency.png")
    # plotQueueOwn(queueTs, queueVal, startAbsTs, endAbsTs, econfig['inferred']['bw_delay_product'],
    #              real_buffer_size, xticks, econfig, RESULT_FILE_PREFIX + "queue.png")
    # plotCwndOwn(cwndData, ssthreshData, startAbsTs, endAbsTs, xticks, RESULT_FILE_PREFIX + "cwnd.png")

    for j in range(num_axes):
        i = 1
        while i * 30 <= econfig['send_duration']:
            #axes[j].axvline(x=i * 30)
            i += 1

    #plt.tight_layout()
    plt.figure('overview')
    #plt.subplots_adjust(wspace, hspace=0.5)
    fig.set_size_inches(num_axes, 3*num_axes)
    if savePlot:
        plt.savefig(RESULT_FILE_PREFIX+'overview.png', dpi=400)
        plt.close(figurename)
    else:
        plt.show()
    logger.info(f"Stats:\n{stats}")

    with open(RESULT_FILE_PREFIX + econfig['stats_file'], 'w+') as statsfile:
        json.dump(stats, statsfile, indent=4)
    logger.info("Overview Plotted")
    plt.clf()
    # Single Plots
    bdp = econfig['inferred']['bw_delay_product']
    real_buffer_size = bdp + econfig['switch_buffer'] * bdp
    '''
    plotLoad("throughput", None,tcpd_data, startTimestamp, endTimestamp, econfig, RESULT_FILE_PREFIX + "throughput.png")
    plotMemory("memory", None, memdata, startAbsTs, endAbsTs, econfig, RESULT_FILE_PREFIX + "memory.png")
    plotLoss("loss", None, tcpd_data, startTimestamp, endTimestamp, econfig, RESULT_FILE_PREFIX + "loss.png")
    plotJitter("jitter", None, tcpd_data, startTimestamp, endTimestamp, econfig, RESULT_FILE_PREFIX + "jitter.png")
    plotLatency("latency", None, tcpd_data, startTimestamp, endTimestamp, econfig, RESULT_FILE_PREFIX + "latency.png")
    plotQueue("queue", None, queueTs, queueVal, startAbsTs, endAbsTs, econfig['inferred']['bw_delay_product'],
                 real_buffer_size, xticks, econfig, RESULT_FILE_PREFIX + "queue.png")
    plotCwnd("cwnd", None, cwndData, ssthreshData, startAbsTs, endAbsTs, xticks, RESULT_FILE_PREFIX + "cwnd.png")
    '''

    logger.info("Opening permissions...")
    os.system("sudo chmod -R 777 " +  RESULT_FILE_PREFIX)
    logger.info("Parsing and plotting finished.")
    plt.close('all')


def external_main(resultfile_prefix):
    plt.figure('overview')
    plt.clf()
    global RESULT_FILE_PREFIX
    RESULT_FILE_PREFIX = resultfile_prefix
    main(savePlot=True)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        plt.figure('overview')
        plt.clf()
        RESULT_FILE_PREFIX = sys.argv[1]
        main(savePlot=True)
    else:
        print("Please provide a result folder.")
