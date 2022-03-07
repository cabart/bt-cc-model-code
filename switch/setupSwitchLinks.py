# add/remove all links at switch
# switch -> receiver interface
# senderX -> switch interfaces

import argparse
import yaml
import sys
import subprocess

import getIfaces

def addSendersDelay(latency_range):
    lat = str(latency_range[0]) + "ms" # TODO: use actual range
    for iface in getIfaces.getSenderifaces():
        try:
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","netem","delay",lat])
        except subprocess.CalledProcessError as e:
            # adding failed, most likely because there already is a root qdisc
            sys.exit(1)


def removeSendersDelay():
    for iface in getIfaces.getSenderifaces():
        try:
            subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root","netem"])
        except subprocess.CalledProcessError as e:
            # removing failed, most likely because there is no netem qdisc setup
            sys.exit(1)


def addReceiverDelay(latency, use_red):
    lat = str(latency) + "ms"
    iface = getIfaces.getReceiveriface()
    try:
        subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","1:0","netem","delay",lat])
        if use_red:
            limit = str(400000)
            avpkt = str(1000)
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","1:1","handle","10:","red","limit",limit,"avpkt",avpkt])
        else:
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","1:1","handle","10:","htb"])
    except subprocess.CalledProcessError as e:
        # adding failed, most likely because there already is a root qdisc
        sys.exit(1)


def removeReceiverDelay():
    iface = getIfaces.getReceiveriface()
    try:
        subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root","netem"])
    except subprocess.CalledProcessError as e:
        # removing failed, most likely because there is no netem qdisc setup
        sys.exit(1)



def main():
    # get arguments
    parser = argparse.ArgumentParser(description='Add or delete delay at network interfaces')
    parser.add_argument('-a', action='store_true', help='add delayed interfaces')
    parser.add_argument('-d', action='store_true', help='delete delayed interfaces')
    args = parser.parse_args()

    # get latency from config file
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()
    latency = config["link_latency"]
    source_latency = config["source_latency"]
    source_latency_range = config["source_latency_range"]
    use_red = config["use_red"]

    if args.a:
        # add interfaces

        # add latency for each sender
        if source_latency:
            addSendersDelay(source_latency_range)
        addReceiverDelay(latency, use_red)

    elif args.d:
        removeSendersDelay()
        removeReceiverDelay()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()