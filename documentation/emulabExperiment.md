# Emulab Experiment

## Notes about setup

Clone the respository using:

> git clone --recurse-submodules git@github.com:cabart/bt-cc-model-code.git

or

> git clone git@github.com:cabart/bt-cc-model-code.git
> git submodule update --init --recursive

Afterwards run the ./setupEnvironment.sh file to finish the setup. Test the setup by running the ./emulab_experiments/testConnectionSetup.sh script, which should retrieve a success message.

- Use a python virtual environment located in 'env/'
- Use geni-lib package located in 'geni-lib/'. This is a submodule and is directly cloned from https://gitlab.flux.utah.edu/emulab/geni-lib.git

The geni-lib package was installed in environment using the following command: '$> env/bin/python -m pip install -e ./geni-lib/'

## Prerequisites

All code is tested on Ubuntu 20.04.

- Credentials for emulab authentication, password for emulab profile (should be in same folder, specified in experiment config file) (Maybe I'll add a option to enter the password at runtime, or make this a one time thing)
- Geni-lib library (directly from github, will be included in my repository) (since there seems to be no consistency in geni-libs documentation and versioning I prefer having a static version of it for every user of my code)
- SSH key for authentication on emulab server (public key must be added at emulab.net)
- SSL config file and Environment variable (will all be included in repository) + running python with 'Sudo -E'

List of all additional software requirements:

- openssl
- realpath (e.g. for testing of serverconnection)

### Old Prerequisites

- Installation of geni-lib ('pip install geni-lib' or 'python -m pip install geni-lib'). Currently the python3 library has python2 statements in it, so some lines of code of the portal.py file need to be changed in order to work. (NOTE: Since the pip version of geni-lib is not up-to-date I would not recommend using it)
- Since code must be run as sudo, dependencies may not work. Use 'sudo /python/env/ ./run_emulab_experiment.py'
- SSH key for authentication on emulab server
- Credentials for emulab authentication, password (TODO: add more details)

## Pipeline

1. run main script (./run_emulab_experiments.py)
2. Allocate resources on Emulab and startup hardware
    -> need a way to get status of experiment and end of experiment
3. Get data from experiment using scp
    -> save all data in results/\<config-name\>/emulab_experiments

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

> hrn:  utahemulab.\<project-name>.\<experiment-name>

> urn:  urn:publicid:IDN+emulab.net:\<project-name>+slice+\<experiment-name>

Server Connection using protogeni:

> hrn:  utahemulab.\<slice-name>

> urn:  urn:publicid:IDN+emulab.net+slice+\<slice-name>

Should try using the base-urn 'urn:publicid:IDN+emulab.net:\<project-name>' to test if easier ssh naming is enabled ('cabart@node.\<project-name>.\<experiment-name>.emulab.net)

## Problems

- Openssl does not work with my certificate (maybe md5 problem), cannot change security level of openssl (why not?)
- Certificates extension 'oid' does not work with newer versions of python cryptograpgy library, should investigate more and maybe ask emulab about it