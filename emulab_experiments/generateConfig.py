#!/usr/bin/python3.8

# Contains methods to generate config file from 

import re
import sys
import time
import math
import subprocess
import os
import threading
from datetime import datetime
import yaml
from collections import Counter
import argparse
import itertools

# not used yet
logfolder = 'hostlogs/'
datafolder = 'hostdata/'
condenseddatafolder = 'condensed/'


# get emulab configuration file
def get_emulab_config(config_name):
    
    with open(config_name, 'r') as config_file:
        config = yaml.safe_load(config_file)
    return config

# infer config settings into default config
def config_edited_copy(default_config, custom):
    config = default_config.copy()
    config.update(custom)
    return config


# Create parameter combinations from original config
def get_config(config_name):

    with open(config_name, 'r') as config_file:
        config = yaml.safe_load(config_file)

    fixed_parameters = config['common_parameters']
    for pox_dir_candidate in config['experiment_parameters']['pox_directory']:
        if os.path.exists(pox_dir_candidate):
            fixed_parameters['pox_directory'] =  pox_dir_candidate
            break
    if 'pox_directory' not in fixed_parameters.keys():
        print("No valid pox_directory found! Aborting...")
        sys.exit(1)

    if 'delete_raw_dump' in config['experiment_parameters'].keys():
        fixed_parameters['delete_raw_dump'] = config['experiment_parameters']['delete_raw_dump']

    param_names = list(config['varying_parameters'].keys())
    config['param_combinations'] = []
    pc_counter = 0
    for param_comb in itertools.product(*[config['varying_parameters'][pn] for pn in param_names]):
        pc_map = fixed_parameters.copy()
        for i in range(len(param_names)):
            param_name = param_names[i]
            if param_name == 'cc_combination':
                N = param_comb[param_names.index('senders')]
                n_adopters_each_protocol = int(N/len(param_comb[i]))
                pc_map['behavior_command'] = '_'.join([ cc+'-'+str(n_adopters_each_protocol) for cc in param_comb[i] ])
            elif param_name == 'qdisc':
                pc_map['use_red'] = True if param_comb[i] == 'RED' else False
            else:
                pc_map[param_names[i]] = param_comb[i]
        #pc_map['name'] = '_'.join([pc_map_key+':'+str(pc_map[pc_map_key]).replace(' ', '') for pc_map_key in pc_map.keys() if pc_map_key != 'pox_directory'])
        pc_map['name'] = str(pc_counter)
        pc_counter += 1
        config['param_combinations'].append(pc_map)

    return config

# Go from behavior config dict to behavior summary string

# Help for parsing. Structure of sending behavior:
# 'sending_behavior': [{'h1': {'protocol': 'tcp-cubic', 'tso_on': False}},
#                       {'h2': {'protocol': 'udp-stable'}}]
def createBehaviorSummary(sending_behavior_dict, config):
    # Lists all protocols that are used
    protocols = [[a['protocol'] for a in client.values()][0] for client in sending_behavior_dict]

    #protocols =[ client['protocol'] for client in sending_behavior_dict]
    counts = Counter(protocols)
    summary = []
    for k in sorted(counts.keys()):
        summary.append(config['behavior_summary_mapping'][k] + '-' + str(counts[k]))
    ret = '_'.join(summary)
    return ret

# Parse the first input
# Create new sending behavior based on string and load it into config.
# Will support old parsing method. '_' for separating behavior types, '-' for parsing the number
# Example string: TCP-8_STABLE-2 will create 8 tcp and 2 udp clients
def parseBehaviorSummary(summaryString, config):
    types = summaryString.split('_')
    hosts = 1
    sending_behavior = []

    for combo in types:
        print(combo)
        if '-' in combo:
            type, num = combo.split('-')
        else:
            num = 1
            type = combo
        behavior = config['send_behavior_parsing'][type]
        for i in range(int(num)):
            sending_behavior.append({'h' + str(hosts): {'protocol': behavior}})
            hosts += 1
    config['sending_behavior'] = sending_behavior


## Result folders are generated growing in depth according to: SEND_DURATION, NSRCHOSTS,
#   LINK_CAPACITY, BUFFER_SIZE, BEHAVIOR_SUMMARY
def generateResultDir(behavior_summary, config):
    if config['base_res_dir']:
        resultDir = config['base_res_dir'] + 'results/'
    else:
        resultDir = 'results/'

    resultParam = [config['send_duration'], config['inferred']['num_senders'],  config['link_capacity'],
                   config['switch_buffer'], behavior_summary]
    for rP in resultParam:
        resultDir += str(rP)+'/'
        if not os.path.exists(resultDir):
            os.system('mkdir -p ' + resultDir)
    resultDir += datetime.strftime(datetime.now(), "%Y-%m-%d--%H-%M-%S") + '/'
    os.system('mkdir -p ' + resultDir)
    for rT in ['hostlogs/', 'hostdata/', 'condensed/']:
        os.mkdir(resultDir+rT)
    config['result_dir'] = resultDir
    return resultDir


# Use the default values for sending behavior to complete the sender configs
def completeSenderConfig(config):
    if not (config['behavior_command'] == None):
        parseBehaviorSummary(config['behavior_command'], config)
    send_defaults = config['defaults']['sending_behavior']
    for sender in config['sending_behavior']:
        if len(sender.keys()) > 1: # Should not happen.
            print("Unexpected number of keys for sender! Keys: ", sender.keys(), '\nConfig: ', config)
        for name in sender.keys():
            props = sender[name]
            # Protocol defaults
            if not 'protocol' in props:
                props['protocol'] = send_defaults['protocol']
            elif props['protocol'] == 'tcp':
                if not 'cc_flavour' in props:
                    props['protocol'] = 'tcp-' + send_defaults['cc_flavour']
                else:
                    props['protocol'] = 'tcp-' + props['cc_flavour']
            elif props['protocol'] == 'udp':
                if not 'udp_sending_behavior' in props:
                    props['protocol'] = 'udp-' + send_defaults['udp_sending_behavior']
                else:
                    props['protocol'] = 'udp-' + props['udp_sending_behavior']
            # TSO Default
            if 'tcp' in props['protocol'] and not 'tso_on' in props:
                props['tso_on'] = send_defaults['tso_on']
    return config


# Create configuration that is either hardcoded or inferred by the default_config
def inferConfig(config):
    inferred = {}
    inferred['num_senders'] = len(config['sending_behavior'])

    linkLatency = config['link_latency']
    linkCapacity = config['link_capacity']
    # packet_size = 1512 # Based on TCP dump of Iperf Traffic. But might need to consider ACK traffic too? (is buffer for both?)
    packet_size = 1514 #

    bw_delay_prod = int(math.ceil(((linkLatency / 1000) * (linkCapacity / 8) * 1e6) / packet_size))
    inferred['bw_delay_product'] = bw_delay_prod
    inferred['buffer_size'] = bw_delay_prod + int(bw_delay_prod * config['switch_buffer'])
    # Sizes as from wireshark and tcpdump
    packetsize_udp = 1512
    payload_udp = 1470

    if config['cbr_as_pss']:
        ppsrate = math.floor(config['link_capacity']*1000000 / (float(packetsize_udp)* 8))
        inferred['cbr_rate'] = ppsrate
    else:
        goodput_ratio_udp = float(payload_udp) / packetsize_udp
        inferred['cbr_rate'] =  goodput_ratio_udp * config['link_capacity'] / float(inferred['num_senders'])

    inferred['cbr_rate'] = inferred['cbr_rate'] * config['cbr_adjustment']

    inferred['behavior_summary'] = createBehaviorSummary(config['sending_behavior'], config)
    config['inferred'] = inferred
    return config


# Create final configuration from experiment configuration
def setup_configuration(config):

    # infer default if sender parameters not set explicitly
    config = completeSenderConfig(config)

    # Infer Configuration
    config = inferConfig(config)
    # Create Result Directory
    resultFilePrefix = generateResultDir(config['inferred']['behavior_summary'], config)  # save it as: 'result_dir' config

    # Dump Config
    f = open(resultFilePrefix + 'config.yaml', 'w')
    yaml.dump(config, f)
    f.close()
    return config
