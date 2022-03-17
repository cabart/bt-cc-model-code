#!/usr/bin/python3.6

## NOTE: as of now: not needed. but if for some reason overview must have different plots than this one, then you can change here

import re
import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import math

logfolder = 'hostlogs/'
datafolder = 'hostdata/'
condenseddatafolder = 'condensed/'

RESULT_FILE_PREFIX = ''

COLORS = {
    'h1': {
        0: (0.0, 0.5, 1.0),
        1: (0.54, 0.81, 0.94)
    },
    'h2': {
        0: (0.8, 0.0, 0.0),
        1: (0.91, 0.45, 0.32)
    },
    'h3': {
        0: (0.0, 0.5, 0.0),
        1: (0.55, 0.71, 0.0)
    },
    'h4': {
        0: (0.5, 0.0, 0.1),
        1: (0.55, 0.71, 0.0)
    },
    'h5': {
        0: (0.2, 0.1, 0.6),
        1: (0.55, 0.71, 0.0)
    },
    'h6': {
        0: (0.5, 0.5, 1.0),
        1: (0.54, 0.81, 0.94)
    },
    'h7': {
        0: (0.5, 0.0, 0.0),
        1: (0.91, 0.45, 0.32)
    },
    'h8': {
        0: (0.5, 0.5, 0.0),
        1: (0.55, 0.71, 0.0)
    },
    'h9': {
        0: (1.0, 0.0, 0.1),
        1: (0.55, 0.71, 0.0)
    },
    'h10': {
        0: (0.7, 0.1, 0.6),
        1: (0.55, 0.71, 0.0)
    },
    'h11': {
        0: (0.7, 0.1, 0.6),
        1: (0.55, 0.71, 0.0)
    },
    'h2-10': {
        0: (0.7, 0.1, 0.6),
        1: (0.55, 0.71, 0.0)
    },
    'h1-10': {
        0: (1.0, 0.0, 0.1),
        1: (0.55, 0.71, 0.0)
    },
}

PLOT_CWND_KEYS = ['10.0.0.1']

# plt.rc('text', usetex=True)
# plt.rc('font', family='serif')
# plt.rcParams['text.latex.preamble'] = [\
#     r'\usepackage{amsmath}',\
#     r'\usepackage{amssymb}']

# For single plot. Needed to be fast, so just duplicated code, sorry
def plotLoadOwn(tcpd_data, starttime, endtime, econfig, destination):
    plt.figure('load')
    plot, ax = plt.subplots()
    num_senders = econfig['inferred']['num_senders']
    linkCap = float(econfig['link_capacity'])
    emulated_bufferCap = econfig['inferred']['bw_delay_product'] * float(econfig['switch_buffer'])
    real_bufferCap = econfig['inferred']['bw_delay_product'] + emulated_bufferCap
    sendBehav = econfig['inferred']['behavior_summary']
    sendBehav = sendBehav.replace('_', ' ')

    effective_duration = endtime - starttime
    converter = float(8.0 / 1e6)  # From bytes to Mbits
    timestep = econfig['plot_load_resolution']

    #print(tcpd_data.total_load[starttime:endtime])

    total_throughput = converter * np.sum(tcpd_data.total_load[starttime:endtime]) / float(effective_duration) # TODO redundant field: total_load
    total_load = 0
    capacity = float(linkCap)
    fair_share = capacity/ float(num_senders)

    plt.hlines([fair_share], starttime, endtime, linestyles='-.', label='Fair Share', colors='orange')
    plt.hlines([capacity], starttime, endtime, linestyles='-.', label='Link Bandwidth Capacity', colors='green')

    sender_throughputs = []
    for hostid in list(range(1, num_senders+1)):
        label = "load_" + str(hostid)
        if label in tcpd_data.columns:
            total_load += np.sum(tcpd_data[label][starttime:endtime])
            average = np.sum(tcpd_data[label][starttime:endtime]) * converter / effective_duration
            sender_throughputs.append(average)
            if hostid in econfig['plot_hosts']:
                ax.plot(tcpd_data.index.values, converter * tcpd_data[label].values / timestep , ":", label=("h%s Throughput" % (hostid)))

    ax.plot(tcpd_data.index.values, converter * tcpd_data['total_load'].values / timestep , ':', label="Total Throughput")
    ax.set_title(r'\textbf{NFlows:} ' + str(num_senders) + r', \textbf{LinkCap:} ' + str(linkCap) + r'Mbps, ' + sendBehav + ', Buffer: ' + str(emulated_bufferCap))
    plt.hlines([total_throughput], starttime, endtime, linestyles='-.', label='Average Throughput', colors='blue')
    ax.set_xlabel(r'Time (s)')
    ax.set_ylabel(r'Rate (Mbps)')
    ax.locator_params(axis=plt, nbins=20)
    ax.set_ylim(bottom=0.0)
    ax.legend(loc=1)
    plt.savefig(destination, dpi=300)

#--------------------------------------------------------------------------------
# Plot congestion control data
def plotCwndOwn(cwndData, ssthreshData, startTimestamp, endTimestamp, xticks, destination):
    plt.figure('cwnd')
    plot, ax = plt.subplots()
    if len(PLOT_CWND_KEYS) == 0:
        return

    plotCwndData = {}
    for origin in PLOT_CWND_KEYS:
        ts = sorted(cwndData[origin].keys())
    
        hostID = re.match(r'.+\.(.+)$', origin).group(1)
        ts = [t for t in ts if float(t) >= startTimestamp and float(t) <= endTimestamp]
        displayTs = [float(t)-startTimestamp for t in ts]
        ax.plot(displayTs, [cwndData[origin][t] for t in ts], label=("h%s" % hostID), color=COLORS["h"+hostID][0], linewidth=0.5)

        # If ts == 0
        if displayTs == []:
            print("In plotCWnd: displayTs is empty. ts: ", ts)
            return

        plotCwndData[origin] = {}
        for i in range(len(ts)):
            plotCwndData[origin]['%.1f' % displayTs[i]] = cwndData[origin][ts[i]]

        ts = sorted(ssthreshData[origin].keys())
        if len(ts) != 0:
            ts = [t for t in ts if float(t) >= startTimestamp and float(t) <= endTimestamp]
            displayTs = [float(t)-startTimestamp for t in ts]
            ax.plot(displayTs, [ssthreshData[origin][t] for t in ts], ':', label=("h%s (ssthresh)" % hostID), color=COLORS["h"+hostID][0])

    with open(RESULT_FILE_PREFIX+'cwndData.json', 'w+') as pDF:
        json.dump(plotCwndData, pDF, sort_keys=True, indent=4)

    ax.set_xlabel(r'Time (s)')
    ax.set_ylabel(r'cwnd (Segments)')
    #ax.set_xticks(range(int(displayTs[-1]+1)))
    #ax.set_xticks(xticks)
    ax.set_ylim(bottom=0.0)
    ax.legend()
    plt.savefig(destination, dpi=300)


# Plot Queue data
# Collect and print
def plotQueueOwn(ts, values, startTimestamp, endTimestamp, bwd_product, real_buffer_size, xticks, econfig, destination):
    plt.figure('queue')
    plot, ax = plt.subplots()
    # Crop
    #print(ts - startTimestamp)
    #print(ts.shape)

    displayTs = [float(ts[i]) - startTimestamp + econfig['truncate_front'] for i in range(ts.shape[0]) if float(ts[i]) >= startTimestamp and float(ts[i]) <= endTimestamp]
    displayValues = [int(values[i])  for i in range(ts.shape[0]) if float(ts[i]) >= startTimestamp and float(ts[i]) <= endTimestamp]
    # Calculate average queue length
    avg_queue = np.average(displayValues)
    ax.plot(displayTs, displayValues, label=("switch1"), linewidth=0.5)

    # Horizontal lines
    ax.plot([displayTs[0], displayTs[-1]], [avg_queue] * 2, '-', label='Buffer Size', color='blue', linewidth=0.5)
    ax.plot([displayTs[0], displayTs[-1]], [real_buffer_size] * 2, '-.', label='Buffer Size', color='green')
    ax.plot([displayTs[0], displayTs[-1]], [bwd_product] * 2, '-.', label='Bandwidth Delay Product', color='orange')
    ax.set_xlabel(r'Time (s)')
    ax.set_ylabel(r'Queue Length (packets)')
    ax.set_ylim(bottom=0.0)
    ax.legend()
    plt.savefig(destination, dpi=300)


def plotLossOwn(tcpd_data, starttime, endtime, econfig, destination):
    plt.figure('loss')
    plot, ax = plt.subplots()
    num_senders = econfig['inferred']['num_senders']
    linkCap = econfig['link_capacity']
    emulated_bufferCap = econfig['inferred']['bw_delay_product'] * float(econfig['switch_buffer'])
    real_bufferCap = econfig['inferred']['bw_delay_product'] + emulated_bufferCap
    sendBehav = econfig['inferred']['behavior_summary']
    sendBehav = sendBehav.replace('_', ' ')
    total_loss = 0
    for hostid in econfig['plot_hosts']:
        label = "loss_" + str(hostid)
        if label in tcpd_data.columns:
            total_loss += np.sum(tcpd_data[label].values)
            ax.plot(tcpd_data.index.values, tcpd_data[label].values, ':', label=("h%s Loss" % (hostid)))

    ax.set_xlabel(r'Time (s)')
    ax.set_ylabel(r'Loss')
    plt.locator_params(axis=ax, nbins=20)
    ax.set_ylim(bottom=0.0)
    ax.legend(loc=1)
    plt.savefig(destination, dpi=300)



def plotLatencyOwn(tcpd_data, starttime, endtime, econfig, destination):
    plt.figure('latency')
    plot, ax = plt.subplots()
    latency_sum = 0
    packet_sum = 0
    for hostid in econfig['plot_hosts']:
        label_lat = "latency_sum_" + str(hostid)
        label_num = "num_" + str(hostid)
        if label_lat in tcpd_data.columns and label_num in tcpd_data.columns:
            latency_sum += np.sum(tcpd_data[label_lat].values)
            packet_sum += np.sum(tcpd_data[label_num].values)
            ax.plot(tcpd_data.index.values, tcpd_data[label_lat].values * (1000.0 / tcpd_data[label_num].values), ':',
                    label=("h%s Latency" % (hostid)))

    ax.set_xlabel(r'Time (s)')
    ax.set_ylabel(r'Latency (ms)')
    plt.locator_params(axis=ax, nbins=20)
    ax.set_ylim(bottom=0.0)
    ax.legend(loc=1)
    plt.savefig(destination, dpi=300)

def plotJitterOwn(tcpd_data, starttime, endtime, econfig, destination):
    plt.figure('jitter')
    plot, ax = plt.subplots()
    num_senders = econfig['inferred']['num_senders']
    linkCap = econfig['link_capacity']
    emulated_bufferCap = econfig['inferred']['bw_delay_product'] * float(econfig['switch_buffer'])
    real_bufferCap = econfig['inferred']['bw_delay_product'] + emulated_bufferCap
    sendBehav = econfig['inferred']['behavior_summary']
    sendBehav = sendBehav.replace('_', ' ')

    jitter_sum = 0.0
    jitter_sum_squared = 0.0
    packet_sum = 0.0
    for hostid in econfig['plot_hosts']:
        label_lat = "jitter_sum_" + str(hostid)
        label_sq_lat = "jitter_sum_sq_" + str(hostid)
        label_num = "num_" + str(hostid)
        if label_lat in tcpd_data.columns and label_num in tcpd_data.columns:
            jitter_sum += np.nansum(tcpd_data[label_lat].values)
            jitter_sum_squared += np.nansum(tcpd_data[label_sq_lat].values)
            packet_sum += np.sum(tcpd_data[label_num].values)
            index = tcpd_data.index.values
            values = tcpd_data[label_lat].values * (1000.0 / tcpd_data[label_num].values)
            stddev = np.sqrt(np.nansum(tcpd_data[label_sq_lat].values) / tcpd_data[label_num].values)
            ax.plot(index, values, ':', label=("h%s average PDV" % (hostid)))
            #ax.errorbar(index, values, stddev, fmt=':', label=("h%s Average Packet Delay Variation" % (hostid)))

    ax.set_xlabel(r'Time (s)')
    ax.set_ylabel(r'Avg. Packet Delay Variation (ms)')
    plt.locator_params(axis=ax, nbins=20)
    ax.set_ylim(bottom=0.0)
    ax.legend(loc=1)
    plt.savefig(destination, dpi=300)

def plotMemoryOwn(df, start, end, econfig, destination):
    plt.figure('memory')
    plot, ax = plt.subplots()
    ts = df[0]
    y_values = df[1]
    base_usage = y_values[0]
    print("base usage: ", base_usage)
    y_values = [int(y_values[i])  for i in range(len(ts)) if float(ts[i]) >= start and float(ts[i]) <= end]
    ts = [float(ts[i]) - start + econfig['truncate_front'] for i in range(len(ts)) if float(ts[i]) >= start and float(ts[i]) <= end]
    y_values = y_values - base_usage
    ax.plot(ts, y_values, "-", label='System Memory Usage')
    average = np.average(y_values)
    plt.savefig(destination, dpi=300)
