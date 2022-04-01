import yaml
import subprocess
import sys
import argparse

# add/remove outgoing latency from receiver -> switch

def getReceiveriface():
    # get all interfaces (format: '<iface> <ip> <macaddress>')
    with open("/var/emulab/boot/ifmap",'r') as f:
        data = [x.split() for x in f.readlines()]

    # only keep ifaces connected to switch
    filtered = filter(lambda x: x[1] == "10.0.0.2", data)
    extendedIfaces = list(filtered)

    iface = extendedIfaces[0][0]
    return iface

def main():
    # get arguments
    parser = argparse.ArgumentParser(description='Add or delete delay at network interface')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', action='store_true', help='add delayed interface')
    group.add_argument('-d', action='store_true', help='delete delayed interface')
    args = parser.parse_args()

    # get latency from config file
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()

    latency = config["link_latency"]
    capacity = config["link_capacity"]
    use_red = config["use_red"]

    # get interface name
    iface = getReceiveriface()
    lat = str(latency) + "ms"
    bandwidth = str(capacity) + "mbit"
    limit = config["inferred"]["buffer_size"]

    if args.a:
        # add interface
        try:
            if use_red:
                subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","5:0","htb","default","1"])
                subprocess.check_output(["sudo","tc","class","add","dev",iface,"parent","5:0","classid","5:1","htb","rate",bandwidth,"burst","15k"])
                subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","5:1","handle","6:","red","limit","1000000","min","30000","max","35000","avpkt","1500","burst","20","bandwidth",bandwidth,"probability","1"])
                subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","6:","handle","10:","netem","delay",lat,"limit",limit])
            else:
                subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","5:0","htb","default","1"])
                subprocess.check_output(["sudo","tc","class","add","dev",iface,"parent","5:0","classid","5:1","htb","rate",bandwidth,"burst","15k"])
                subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","5:1","handle","10:","netem","delay",lat,"limit",limit])
        
        except subprocess.CalledProcessError as e:
            # adding failed, most likely because there already is a root qdisc
            sys.exit(1)
        #try:
        #    subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","netem","delay",lat,"rate",cap])
        #except subprocess.CalledProcessError as e:
        #    # adding failed, most likely because there already is a root qdisc
        #    sys.exit(1)
    elif args.d:
        # remove interface
        try:
            subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root"])
        except subprocess.CalledProcessError as e:
            # removing failed, most likely because there is no netem qdisc setup
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()