# Todo list

## Main Goals

- [x] General experiment structure (starting, stopping), and API interaction
- [x] Doing all measurements automatically
- [x] Parsing all data and saving them on local machine
- [ ] Add support for all relevant CC-algorithms (i.e. BBR) TODO: test this
- [ ] Reviewing gathered data and checking validity

## General

- [x] add logparser to run_emulab_experiment as it is working now
- [ ] check if results do make sense and compare them to mininet experiments
- [x] add ipv6 disabling (quite straigthforward), how to enable it again afterwards? Is it enough to reset all values to 0?
- [x] add mention of installing apt-get packages (latex,...) in documentation and add install script (maybe add this to setup script)
- [ ] adapt general naming scheme of sender and receiver from 'senderX', 'receiver' to 'hX', 'hDest' (X starting from 1 instead of 0) to be more in line with Simons code. Beware of many files which have to be adapted and tested!
- [ ] change emulab_connection.py to renew slice for multiple successive experiments on one day (otherwise slice may expire during experiment)
- [ ] clean up code and naming conventions
- [ ] adapt run_emulab_script, make it more functional and clear, add a connection class/object for all ssh connections and node names
- [ ] could compress all files that are downloaded, this could lead to faster download times especially for large experiments with large bandwidth
- [ ] Delete unneeded data after experiment to save disk space

## sender

- [ ] add more debugging to remote_logparser.py
- [ ] look into failing of parsing some packets
- [x] disable ipv6 script (run all commands as sudo)
- [x] add BBR support (install everything necessary when starting up computers)

## receiver

- [ ] same as sender otherwise nothing left to do for now

## switch

- [ ] add logging for switch_setup_link.py
- [ ] weird queue measurements behavior discovered, sometimes only one backlog result (what is the reason for this?)
- [ ] check ovs setup, maybe should add more dynamic behaviour regarding interface names (eth1,eth2,...) and use emulab setup files instead

## Errors

- [ ] https://gitlab.inf.ethz.ch/simonsch/cc-de-models/-/blob/master/mininet_experiments/ccexperiment.py#L64 should have brackets for arguments