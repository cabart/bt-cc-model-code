# Emulab Experiment

## Prerequisites

All code was tested on Ubuntu 20.04.

All configuration changes need to be made in [config file](../emulab_experiments/emulab_config.yaml).

- Credentials for Emulab authentication (Emulab login)
  - Emulab password can be saved in a file and referenced to in config file, or be typed in at runtime during the experiment
- SSH key for authentication on emulab server
  - Public key must be added at emulab.net and be referenced to in config file (for ssh connection during experiment)

Note: All paths in config file are relative pathes to 'home' path (also part of config file).

## Dependencies

Install all dependencies by running the setup script:

~~~bash
sudo ./setup_environment.sh
~~~

Geni-lib library should work out of the box if it was installed as described in [README](../README.md).

- Geni-lib library (directly from github, will be included in my repository) (since there seems to be no consistency in geni-libs documentation and versioning I prefer having a static version of it for every user)

- python libraries (see [libraries](../requirements/requirements.txt))

- system packages (apt packages)
  - texlive-latex-extra
  - cm-super
  - dvipng

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
    - save all data in results/\<config-name\>/emulab_experiments/...
6. Shutdown hardware (or repeat for multiple experiments)

Program code:

1. Generate config for all experiments and all possible parameter configurations
2. Create emulab topology for all experiments -> limitations are stricter than for minilab experiments
    - different number of senders is critical
    - link capacity has to be set to maximum
    - set link latency at start of individual experiment (same for multiple runs of same configuration)

## Folder Structures

~~~bash
/local
  - configs
  - documentation
  - emulab_experiments
    - remote_scripts
      - remote_lib
  - env
  - geni-lib
  - requirements
  - results
  - testing
~~~

- configs
  - includes all config files for different setups
- documentation
  - includes more detailed explenations about project
- emulab_experiments
  - includes all relevant scripts to run emulab experiments
  - remote_scripts, includes all scripts running on any remote computer (sender, switch, receiver)
- env
  - python environment for experiment
- geni-lib
  - geni-lib library for generating rspec files (is a github repository itself)
- requirements
  - all python requirements
- results
  - where all experiment results are saved (if default config is not changed)
  - does not exist if no experiment has been run yet
- testing
  - includes a couple of scripts for playing around, not used for actual experiment just for debugging
  - may be removed in final product

### result directory

~~~bash
/path/to/results/
  - condensed
  - hostdata
  - hostlogs
  - queue
~~~

- condensed
  - compressed versions of tcpdump files (one from every sender and receiver, plus one consisting of all data summarized in one file *tcpd_dataframe.csv*)
- hostdata
  - uncompressed tcpdump data (only available on remote nodes). These files are being compressed and minimized on remote nodes and sent to condensed folder of local experiment pc.
- hostlogs
  - All logging data from remote nodes. If there are errors on remote nodes they will be reported in this files. Also hold congestion window data from all nodes.
- queue
  - Holds data from switch queue measurements

## Some notes about send and receive node scripts

Get the interface name on any node by using the information from */var/emulab/boot/ifmap* on any remote node.

**Information below is a bit out of date:**

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
- capacity of switch/receiver link (use same capacity on senderX/switch link to ensure bottleneck link is the switch/receiver link)
- qdisc (queuing discipline)

### Per sender

- latency
- congestion control algorithm
- tso

- mss
- cbr_as_pss
- cbr_rate

## Questions

- Which part of base_config is static?

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

*Exclusive virtual machines* can be viewed as regular nodes and communicated to using port 22!

~~Should try using the base-urn 'urn:publicid:IDN+emulab.net:\<project-name>' to test if easier ssh naming is enabled ('cabart@node.\<project-name>.\<experiment-name>.emulab.net)~~

## Problems

- Certificates extension 'oid' does not work with newer versions of python cryptography library, should investigate more and maybe ask emulab about it
