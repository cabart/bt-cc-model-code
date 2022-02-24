# mininet setup

## Setup VM
Use VM (e.g. in virtualbox): [mininet VM download](http://mininet.org/download/)
(Native installation does not work in WSL since not all queing disciplines are supported, and can not easily be added).
Download Ubuntu 20.04 version for bbr2 support.

### Setup port-forwarding for ssh access to VM

For Linux:
> ssh -Y -l mininet -p 2222 localhost

For WSL:
> ssh -Y -l mininet -p 2222 "$(hostname).local"

To avoid typing a password each time copy your *public* ssh key to the VM as described in [VM setup](http://mininet.org/vm-setup-notes/).

Run on host:
> scp -P 2222 ~/.ssh/id_rsa.pub mininet@"$(hostname).local":~/

Run on VM:
> cd ~/ && mkdir -p .ssh && chmod 700 .ssh && cd .ssh && touch authorized_keys2 && chmod 600 authorized_keys2 && cat ../id_rsa.pub >> authorized_keys2 && rm ../id_rsa.pub && cd ..

Note: Change name of the key to your key.
