import yaml
import subprocess

def getReceiveriface():
    # get all interfaces (format: '<iface> <ip> <macaddress>')
    with open("/var/emulab/boot/ifmap",'r') as f:
        data = [x.split() for x in f.readlines()]

    # only keep ifaces connected to switch
    filtered = filter(lambda x: x[1] == "10.0.0.2", data)
    extendedIfaces = list(filtered)

    iface = extendedIfaces[0][0]
    return iface

def main(latency):
    # add outgoing latency from receiver -> switch
    iface = getReceiveriface()

    lat = str(latency) + "ms"
    out = subprocess.check_output(["tc","qdisc","add","dev",iface,"root","netem","delay",lat]).decode("utf-8")
    return out
    

if __name__ == "__main__":
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()

    linkLatency = config["link_latency"]

    main(linkLatency)