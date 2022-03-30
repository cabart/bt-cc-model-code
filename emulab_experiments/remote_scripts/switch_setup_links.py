# add/remove all links at switch
# switch -> receiver interface
# senderX -> switch interfaces

import argparse
import yaml
import sys
import subprocess

import switch_get_ifaces

def addSendersLimits(latency_range, source_latency, capacity):
    # TODO: use correct latency
    lat = str(latency_range[0]) + "ms" # TODO: use actual range
    bandwidth = str(capacity) + "mbit"
    for iface in switch_get_ifaces.getSenderifaces():
        try:
            if source_latency:
                subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","netem","delay",lat])
            else:
                # don't need to setup link at all
                pass

        except subprocess.CalledProcessError as e:
            # adding failed, most likely because there already is a root qdisc
            sys.exit(1)


def removeSendersLimits():
    # TODO: check if this throws an error if no queue is initialized
    for iface in switch_get_ifaces.getSenderifaces():
        try:
            subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root","netem"])
        except subprocess.CalledProcessError as e:
            # removing failed, most likely because there is no netem qdisc setup
            #sys.exit(1)
            print("removing failed, probably no netem set up due to zero latency")
            pass


def addReceiverLimits(latency, use_red, capacity):
    lat = str(latency) + "ms"
    iface = switch_get_ifaces.getReceiveriface()
    bandwidth = str(capacity) + "mbit"
    try:
        if use_red:
            limit = str(400000)
            avpkt = str(1000)
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","1:0","red","limit",limit,"avpkt",avpkt,"bandwidth",bandwidth])
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"handle","2:0","parent","1:0","netem","delay",lat,"rate",bandwidth])
        else:
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","1:","htb","default","1"])
            subprocess.check_output(["sudo","tc","class","add","dev",iface,"parent","1:","classid","1:1","htb","rate",bandwidth])
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","1:1","handle","10:","netem","delay",lat,"rate",bandwidth])
        
    except subprocess.CalledProcessError as e:
        # adding failed, most likely because there already is a root qdisc
        sys.exit(1)


def removeReceiverLimits():
    iface = switch_get_ifaces.getReceiveriface()
    try:
        subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root"])
    except subprocess.CalledProcessError as e:
        # removing failed, most likely because there is no netem qdisc setup
        sys.exit(1)


def main():
    # get arguments
    parser = argparse.ArgumentParser(description='Add or delete delay at network interfaces')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', action='store_true', help='add delayed interfaces')
    group.add_argument('-d', action='store_true', help='delete delayed interfaces')
    args = parser.parse_args()

    # get latency from config file
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()
    latency = config["link_latency"]
    capacity = config["link_capacity"]
    source_latency = config["source_latency"]
    source_latency_range = config["source_latency_range"]
    use_red = config["use_red"]

    bufferFactor = config["switch_buffer"]
    bw_delay_product = config["inferred"]["bw_delay_product"]

    if args.a:
        # add interfaces

        # add latency for each sender
        addSendersLimits(source_latency_range, source_latency, capacity)
        addReceiverLimits(latency, use_red, capacity)

    elif args.d:
        removeSendersLimits()
        removeReceiverLimits()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()