# Todo list

## Main Goals

- [x] General experiment structure (starting, stopping), and API interaction
- [x] Doing all measurements automatically
- [x] Parsing all data and saving them on local machine
- [x] Add support for BBR
- [ ] Add support for BBR2
- [ ] Reviewing gathered data and checking validity
- [ ] Run big_experiment.yaml once everything else is running correctly

## General

- [x] add logparser to run_emulab_experiment as it is working now
- [x] check if results do make sense and compare them to mininet experiments
- [x] add ipv6 disabling (quite straigthforward), how to enable it again afterwards? Is it enough to reset all values to 0?
- [x] add mention of installing apt-get packages (latex,...) in documentation and add install script (maybe add this to setup script)
- [x] adapt general naming scheme of sender and receiver from 'senderX', 'receiver' to 'hX', 'hDest' (X starting from 1 instead of 0) to be more in line with Simons code. Beware of many files which have to be adapted and tested! -> hDest doesn't work since emulab does not allow capital letters in node names, used 'hdest' instead
- [x] change emulab_connection.py to renew slice for multiple successive experiments on one day (otherwise slice may expire during experiment)
- [x] clean up code and naming conventions
- [x] adapt run_emulab_script, make it more functional and clear, add a connection class/object for all ssh connections and node names
- [x] could compress all files that are downloaded, this could lead to faster download times especially for large experiments with large bandwidth
- [x] Delete unneeded data after experiment to save disk space
- [x] Add sample iperf run to test theoretical bandwidth (since it might be lower than expected)
- [x] Add debug for used hardware on emulab side
- [x] Solve compression by using flag, instead of manually doing it
- [x] Fix issue where downloading begins before logparsers have finished

## sender

- [x] add more debugging to remote_logparser.py
- [x] look into failing of parsing some packets
- [x] disable ipv6 script (run all commands as sudo)
- [x] add BBR support (install everything necessary when starting up computers)
- [x] add ping logging to test if link latencies are correct

## receiver

- [x] same as sender otherwise nothing left to do for now

## switch

- [x] add logging for switch_setup_link.py
- [x] weird queue measurements behavior discovered, sometimes only one backlog result (what is the reason for this?)
- [x] check ovs setup, maybe should add more dynamic behaviour regarding interface names (eth1,eth2,...) and use emulab setup files instead

## Known issues

- [ ] in rare cases 'slice does not exist' occurs even though it exists
