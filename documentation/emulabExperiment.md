# Emulab Experiment

## Prerequisites

All code was tested on Ubuntu 20.04.

All configuration changes need to be made in [config file](../emulab_experiments/emulab_config.yaml).

- Credentials for Emulab authentication (Emulab login)
  - Emulab password can be saved in a file and referenced to in config file, or be typed in at runtime during the experiment
- SSH key for authentication on emulab server
  - Public key must be added at emulab.net and be referenced to in config file (for ssh connection during experiment)

Note: All paths in config file are relative pathes to 'home' path (also part of config file).

~- SSL config file and Environment variable (will all be included in repository) + running python with 'Sudo -E'~ not used anymore

## Dependencies

- Geni-lib library (directly from github, will be included in my repository) (since there seems to be no consistency in geni-libs documentation and versioning I prefer having a static version of it for every user)

List of all additional software requirements:

Currently none

~~- openssl~~

~~- realpath (e.g. for testing of serverconnection)~~

not needed anymore

## Pipeline of ./run.sh (and ./run_emulab_experiments.py)

1. run main script (./run_emulab_experiments.py) with some config
2. Allocate resources on Emulab and startup hardware
    - Uses the emulabConnection file/class for handling resources and experiment status/setup/shutdown which in turn communicates with the emulab server using xmlrpc
3. Wait for hardware setup to complete
    - Setting up of virtual switch on a virtual machine might take up to ~10min
4. Start experiment, using ssh connections to all remote hardware resources
    - Upload config file to all nodes
    - start receiving script on receiver
    - start sending script on sender
5. Get data from experiment using scp
    - save all data in results/\<config-name\>/emulab_experiments
6. Shutdown hardware (or repeat for multiple experiments)

Program code:

1. Generate config for all experiments and all possible parameter configurations
2. Create emulab topology for all experiments -> limitations are stricter than for minilab experiments
    - different number of senders is critical
    - link capacity has to be set to maximum
    - set link latency at start of individual experiment
    - How to handle source_latency_range, qdisc, switch_buffer?

## Folder Structures

### receiver

~~~bash
/local
  - cc-model-code-main?
  - results
    - iperf_s_tcp.log | iperf_s_udp.log (or according to config)
  receiver.log
~~~

### senderX

~~~bash
/local
  - cc-model-code-main?
  - results
    - 
  senderX.log
~~~

## Some notes about send and receive node scripts

Get the interface name for sending data into the experiment network

~~~bash
ip route show 10.0.0.0/24 | grep -o "dev \S* " | grep -o " \S*"
~~~

Ideally when doing this in python, do the _ip_ command with popen and do the grep part with regular expressions (re)

~~~python
output = subprocess.check_output(["ip","route","show","10.0.0.0/24"]).decode("utf-8")
pattern = re.compile('dev \S*')
result = pattern.findall(output)[0].split()[1]
print(result)
~~~

## Parameters

### Per experiment

- send duration
- number of sender
- capacity

### Per sender

- latency
- qdisc (queuing discipline)
- tso

- mss
- cbr_as_pss
- cbr_rate

## Questions

- Which part of base_config is static?
- How to get parameters onto each sender/receiver?

## Notes about server connection

Server Connection over emulab:

~~~bash
hrn:  utahemulab.\<project-name>.\<experiment-name>

urn:  urn:publicid:IDN+emulab.net:\<project-name>+slice+\<experiment-name>

ssh -p 22 \<user_name>@\<node-name>.\<experiment_name>.\<project_name>.emulab.net
~~~

Server Connection using protogeni:

~~~bash
hrn:  utahemulab.\<slice-name>

urn:  urn:publicid:IDN+emulab.net+slice+\<slice-name>

ssh -p 22 \<user_name>@\<node-name>.\<sliver_name>.emulab-net.emulab.net
~~~

For virtual machines: Use a specific port (given at runtime)

~~Should try using the base-urn 'urn:publicid:IDN+emulab.net:\<project-name>' to test if easier ssh naming is enabled ('cabart@node.\<project-name>.\<experiment-name>.emulab.net)~~

## Problems

- Certificates extension 'oid' does not work with newer versions of python cryptograpgy library, should investigate more and maybe ask emulab about it
