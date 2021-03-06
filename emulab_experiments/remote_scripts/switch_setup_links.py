# add/remove all links at switch
# switch -> receiver interface
# senderX -> switch interfaces

import argparse
import yaml
import sys
import subprocess
from remote_lib import remote

import switch_get_ifaces

RED_CORRECTION_FACTOR = {
    0.5: 83/79,
    1.0: 83/75,
    2.0: 83/69,
    3.0: 83/68,
    4.0: 83/58,
    5.0: 83/68, # 78
    6.0: 83/58,
    7.0: 83/51  # 57
}

def addSendersLimits(sending_behavior, logger):
    for host in sending_behavior:
        for hostname,properties in host.items():
            iface = switch_get_ifaces.getSenderiface(hostname)
            lat = str(properties["latency"]) + "ms"
            logger.info("add latency: {}, {}, {}".format(hostname,iface,lat))
            try:
                subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","netem","delay",lat])
            except subprocess.CalledProcessError as e:
                logger.error("Could not setup link: {}".format(e))
            

def removeSendersLimits(sending_behavior, logger):
    # TODO: check if this throws an error if no queue is initialized
    for host in sending_behavior:
        for hostname in host.keys():
            iface = switch_get_ifaces.getSenderiface(hostname)
            try:
                subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root","netem"])
            except subprocess.CalledProcessError as e:
                # removing failed, most likely because there is no netem qdisc setup
                logger.error("removing failed, probably no netem set up due to zero latency")


def addReceiverLimits(latency, use_red, capacity, queue_length, max_queue_size, link_size, logger):
    lat = str(latency) + "ms"
    iface = switch_get_ifaces.getReceiveriface()
    bandwidth = str(capacity) + "Mbit"
    limit = str(queue_length)

    logger.info("Add receiver link setup: latency {}, bandwidth {}, queue_size {}, iface {}".format(lat,bandwidth,limit,iface))
    try:
        subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"root","handle","5:0","htb","default","1"])
        subprocess.check_output(["sudo","tc","class","add","dev",iface,"parent","5:0","classid","5:1","htb","rate",bandwidth,"burst","15k"])
        parent = "5:1"
        if use_red:
            subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent","5:1","handle","6:","red","limit",str(3*max_queue_size),"min",str(link_size),"max",str(max_queue_size),"avpkt","1514","burst",str(int((2*link_size+max_queue_size)/3000)+1),"bandwidth",bandwidth,"probability","1"])
            parent = "6:"
        subprocess.check_output(["sudo","tc","qdisc","add","dev",iface,"parent",parent,"handle","10:","netem","delay",lat,"limit",limit])
        
    except subprocess.CalledProcessError as e:
        # adding failed, most likely because there already is a root qdisc
        logger.error("Setting up receiver link failed")


def removeReceiverLimits(logger):
    iface = switch_get_ifaces.getReceiveriface()
    try:
        subprocess.check_output(["sudo","tc","qdisc","del","dev",iface,"root"])
    except subprocess.CalledProcessError as e:
        # removing failed, most likely because there is no netem qdisc setup
        logger.error("Removing receiver interface setup failed")


def main():
    # get logger
    logger = remote.getLogger("switch_setup_links")
    logger.info("Started switch link setup")

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

    queue_length = config["inferred"]["buffer_size"]
    switch_buffer = config["switch_buffer"]
    bw_delay_product = config["inferred"]["bw_delay_product"]
    link_size = bw_delay_product * RED_CORRECTION_FACTOR[switch_buffer] if use_red else bw_delay_product
    max_queue_size = int(switch_buffer * bw_delay_product) + bw_delay_product
    logger.info(f"Queue_length {queue_length}, max_queue_size {max_queue_size}")
    link_size = int(link_size*1514)
    max_queue_size = int(max_queue_size*1514)

    if args.a:
        # add interfaces
        logger.info("Add switch interfaces")

        # add latency for each sender
        if source_latency:
            addSendersLimits(config["sending_behavior"], logger)
        addReceiverLimits(latency, use_red, capacity, queue_length, max_queue_size, link_size, logger)

    elif args.d:
        logger.info("Remove switch interfaces")
        if source_latency:
            removeSendersLimits(config["sending_behavior"], logger)
        removeReceiverLimits(logger)
    else:
        parser.print_help()
        sys.exit(1)

    logger.info("Show switch interfaces")
    try:
        output = subprocess.check_output(["sudo","tc","qdisc","show"]).decode("utf-8")
        logger.info(output)
        logger.info("---")
    except:
        logger.error("could not show interface setup")

    logger.info("Finished setting up switch setup links")

if __name__ == "__main__":
    main()