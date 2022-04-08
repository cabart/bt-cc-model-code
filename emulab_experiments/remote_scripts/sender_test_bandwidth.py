import subprocess
import re

path = '/local/bandwidth-test.log'
fout = open(path,'w')

# ping to ensure route to host exists
cmd = 'ping 10.0.0.2 -c 3'
proc = subprocess.Popen(cmd.split(), stdout=fout, stderr=fout)
stdout, stderr = proc.communicate()
fout.write("stdout: " + str(stdout) + "\n")
fout.write("stderr: " + str(stderr) + "\n")

# do iperf measurement
cmd = 'iperf -c 10.0.0.2 -p 5002 -e -t 10 -f m'
proc = subprocess.Popen(cmd.split(), stdout=fout, stderr=fout)

proc.communicate()
rc = proc.returncode
fout.close()

if rc == 0:
    f = open(path,'r')
    last = f.readlines()[-1]
    f.close()

    print(last)
    bandwidth = re.findall('(\d+) Mbits/sec', last)[0]
    print("bandwidth:",bandwidth)
else:
    print("return code: ",str(rc),"0 Mbits/sec")