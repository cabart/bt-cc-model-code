import subprocess

fout = open('/local/bandwidth-test.log')
cmd = 'iperf -c 10.0.0.2 -B 10.0.0.2 -p 5002 -e -t 10 -f MBytes'
proc = subprocess.Popen(cmd, stdout=fout)

proc.communicate()
fout.close()