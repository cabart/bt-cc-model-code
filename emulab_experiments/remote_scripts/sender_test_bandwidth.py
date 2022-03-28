import subprocess
import re

path = '/local/bandwidth-test.log'
fout = open(path,'w')
cmd = 'iperf -c 10.0.0.2 -p 5002 -e -t 10 -f m'
proc = subprocess.Popen(cmd.split(), stdout=fout)

proc.communicate()
fout.close()

f = open(path,'r')
last = f.readlines()[-1]
f.close()

bandwidth = re.findall('(\d+) Mbits/sec', last)[0]
print("bandwidth:",bandwidth)