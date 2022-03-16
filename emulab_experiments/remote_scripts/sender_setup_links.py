import yaml
import subprocess
import sys
import argparse
import re

# add/remove outgoing latency from sender -> switch

def getSenderIface(senderNumber):
    ifaceNumber = senderNumber + 3
    # get all interfaces (format: '<iface> <ip> <macaddress>')
    with open("/var/emulab/boot/ifmap",'r') as f:
        data = [x.split() for x in f.readlines()]

    # only keep ifaces connected to switch
    address = "10.0.0." + str(ifaceNumber)
    filtered = filter(lambda x: x[1] == address, data)
    extendedIfaces = list(filtered)

    iface = extendedIfaces[0][0]
    return iface

def main():
    # get arguments
    parser = argparse.ArgumentParser(description='Add or delete delay at network interface')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', action='store_true', help='add delayed interface')
    group.add_argument('-d', action='store_true', help='delete delayed interface')
    args = parser.parse_args()

    # get latency from config file
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()

    # get sender number
    pattern = re.compile('sender[0-9]+')
    number = re.compile('[0-9]+')
    hostname = subprocess.check_output(["hostname"]).decode("utf-8") # e.g. sender3.experiment-name...
    senderNumber = number.findall(pattern.findall(hostname)[0])[0]

    hostname = "h" + senderNumber
    latency = ""
    dic = config["sending_behavior"][int(senderNumber)]
    for val in dic.values():
        latency = val["latency"]

    print("latency:",latency)
                
    capacity = config["link_capacity"]

    # get interface name
    iface = getSenderIface(int(senderNumber))
    print(iface)
    lat = str(latency) + "ms"
    cap = str(capacity) + "mbit"

    if args.a:
        # add interface
        try:
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","netem","delay",lat,"rate",cap])
        except subprocess.CalledProcessError as e:
            # adding failed, most likely because there already is a root qdisc
            sys.exit(1)
    elif args.d:
        # remove interface
        try:
            subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root","netem"])
        except subprocess.CalledProcessError as e:
            # removing failed, most likely because there is no netem qdisc setup
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()