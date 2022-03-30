import yaml
import subprocess
import sys
import argparse
import re

# add/remove outgoing latency from sender -> switch

def getSenderIface(senderNumber):
    ifaceNumber = senderNumber + 2
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

    # if no source latency, nothing to do
    if not config["source_latency"]:
        print("no setup needed")
        sys.exit(0)

    # get sender number
    hostname_pattern = re.compile('h\d+')
    hostnumber_pattern = re.compile('h(\d+)')
    full_hostname = subprocess.check_output(["hostname"]).decode("utf-8") # e.g. h3.experiment-name...

    sender_number = hostnumber_pattern.findall(full_hostname)[0]
    hostname = hostname_pattern.findall(full_hostname)[0]
    print("sender number:", sender_number)
    print("full hostname:", full_hostname)
    print("hostname:", hostname)

    latency = ""
    for x in config["sending_behavior"]:
        if hostname in x.keys():
            latency = x[hostname]["latency"]
            break
    print("latency:", latency)

    if latency == "":
        print("no latency found")
        sys.exit(1)

    # get interface name
    iface = getSenderIface(int(sender_number))
    print("network interface:", iface)
    lat = str(latency) + "ms"

    if args.a:
        # add interface
        try:
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","netem","delay",lat])
        except subprocess.CalledProcessError as e:
            # adding failed, most likely because there already is a root qdisc
            print("adding latency at sender failed")
            sys.exit(1)
    elif args.d:
        # remove interface
        try:
            subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root","netem"])
        except subprocess.CalledProcessError as e:
            # removing failed, most likely because there is no netem qdisc setup
            print("removing latency at sender failed")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()