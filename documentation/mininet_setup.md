# mininet setup

This is a minimalistic guide to install a VM which runs mininet and how to access the VM from outside. It was only used to test mininet code.

## Setup VM

Use VM (e.g. in virtualbox): [mininet VM download](http://mininet.org/download/)
(Native installation does not work in WSL (Windows-Subsystem for Linux) since not all queing disciplines are supported, and can not easily be added).
Download Ubuntu 20.04 version for BBR support.

### Setup port-forwarding for ssh access to VM

For Linux:

~~~bash
ssh -Y -l mininet -p 2222 localhost
~~~

For WSL:

~~~bash
ssh -Y -l mininet -p 2222 "$(hostname).local"
~~~

To avoid typing a password each time copy your *public* ssh key to the VM as described in [VM setup](http://mininet.org/vm-setup-notes/).

Run on host:

~~~bash
scp -P 2222 ~/.ssh/id_rsa.pub mininet@"$(hostname).local":~/
~~~

Run on VM:

~~~bash
cd ~/ && mkdir -p .ssh && chmod 700 .ssh && cd .ssh && touch authorized_keys2 && chmod 600 authorized_keys2 && cat ../id_rsa.pub >> authorized_keys2 && rm ../id_rsa.pub && cd ..
~~~

Note: Change name of the key to your key.
