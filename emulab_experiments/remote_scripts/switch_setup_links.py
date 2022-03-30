# add/remove all links at switch
# switch -> receiver interface
# senderX -> switch interfaces

import argparse
import yaml
import sys
import subprocess

import switch_get_ifaces

def addSendersLimits(sending_behavior):
    for host in sending_behavior:
        for hostname,properties in host.items():
            iface = switch_get_ifaces.getSenderiface(hostname)
            lat = str(properties["latency"]) + "ms"
            print("add latency:",hostname,iface,lat)
            try:
                subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","netem","delay",lat])
            except subprocess.CalledProcessError as e:
                print("Error:",e)
                sys.exit(1)


def removeSendersLimits(sending_behavior):
    # TODO: check if this throws an error if no queue is initialized
    for host in sending_behavior:
        for hostname in host.keys():
            iface = switch_get_ifaces.getSenderiface(hostname)
            try:
                subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root","netem"])
            except subprocess.CalledProcessError as e:
                # removing failed, most likely because there is no netem qdisc setup
                print("removing failed, probably no netem set up due to zero latency")


def addReceiverLimits(latency, use_red, capacity):
    lat = str(latency) + "ms"
    iface = switch_get_ifaces.getReceiveriface()
    bandwidth = str(capacity) + "mbit"
    burst = "15k" # TODO: calculate this
    limit = "13" # TODO: calculate this

    try:
        if use_red:
            #limit = str(400000)
            #avpkt = str(1000)
            #subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","1:0","red","limit",limit,"avpkt",avpkt,"bandwidth",bandwidth])
            #subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"handle","2:0","parent","1:0","netem","delay",lat,"rate",bandwidth])

            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","5:0","htb","default","1"])
            subprocess.check_output(["sudo","tc","class","add","dev",iface,"parent","5:0","classid","5:1","htb","rate",bandwidth,"burst",burst])
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","5:1","handle","6:","red","limit","1000000","min","30000","max","35000",avpkt,"1500",burst,"20","bandwidth",bandwidth,"probability","1"])
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","6:","handle","10:","netem","delay",lat,"limit",limit])
        else:
            #subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","1:","htb","default","1"])
            #subprocess.check_output(["sudo","tc","class","add","dev",iface,"parent","1:","classid","1:1","htb","rate",bandwidth])
            #subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","1:1","handle","10:","netem","delay",lat,"rate",bandwidth])

            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","5:0","htb","default","1"])
            subprocess.check_output(["sudo","tc","class","add","dev",iface,"parent","5:0","classid","5:1","htb","rate",bandwidth,"burst",burst])
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","5:1","handle","10:","netem","delay",lat,"limit",limit])
        
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
    use_red = config["use_red"]

    bufferFactor = config["switch_buffer"]
    bw_delay_product = config["inferred"]["bw_delay_product"]

    if args.a:
        # add interfaces

        # add latency for each sender
        if source_latency:
            addSendersLimits(config["sending_behavior"])
        addReceiverLimits(latency, use_red, capacity)

    elif args.d:
        if source_latency:
            removeSendersLimits()
        removeReceiverLimits()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()