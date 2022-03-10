import yaml
import getIfaces
import re
import subprocess
import time
import os

# need to stop this file to stop queue measurements
def main():
    # get config file
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()

    result_file = os.path.join(config['result_dir'],"queue_length.csv")
    sample_period = config['tc_queue_sample_period']

    dev_name = getIfaces.getReceiveriface()

    queue_pattern = re.compile(r'backlog\s[^\s]+\s([\d]+)p')
    cmd = "tc -s qdisc show dev " + dev_name
    output_file = open(result_file, "w")

    while True:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = p.stdout.read()
        #print(output)
        matches = queue_pattern.findall(str(output)) # Usually two matches: First match is HTB or RED, Second is NetEm
        if matches == []:
            print("No match found.")
            break
        if len(matches) == 1:
            print("Only one match found. Untypical")
            output_file.write(("%.6f,%s" % time.time(), str(matches[0])))
        else:
            output_file.write("%.6f,%s,%s\n" % (time.time(), str(matches[0]), str(matches[1])))
        time.sleep(sample_period)



if __name__ == "__main__":
    main()