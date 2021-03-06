import yaml
import switch_get_ifaces
import re
import subprocess
import time
import os
import signal
from remote_lib import remote

class Killer:
    killed = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_program)
        signal.signal(signal.SIGTERM, self.exit_program)
    
    def exit_program(self, *args):
        self.killed = True

# need to stop this file to stop queue measurements
def main():
    # get config file
    f = open("/local/config.yaml", "r")
    config = yaml.safe_load(f)
    f.close()

    resultPath = os.path.join("/local",config['result_dir'])
    remote.createFolderStructure(resultPath)

    result_file = os.path.join(resultPath,"queue/queue_length.csv")
    sample_period = config['tc_queue_sample_period']

    dev_name = switch_get_ifaces.getReceiveriface()

    queue_pattern = re.compile(r'backlog\s[^\s]+\s([\d]+)p')
    cmd = "tc -s qdisc show dev " + dev_name
    output_file = open(result_file, "w")

    killer = Killer()
    while not killer.killed:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = p.stdout.read()
        #print(output)
        matches = queue_pattern.findall(str(output)) # Usually two matches: First match is HTB or RED, Second is NetEm
        if matches == []:
            print("No match found.")
            break
        if len(matches) == 1:
            print("Only one match found. Untypical")
            output_file.write(("%.6f,%s\n" % (time.time(), str(matches[0]))))
        else:
            output_file.write("%.6f,%s,%s\n" % (time.time(), str(matches[0]), str(matches[1])))
        time.sleep(sample_period)
    output_file.close()



if __name__ == "__main__":
    main()