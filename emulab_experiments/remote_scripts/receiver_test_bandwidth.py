import subprocess

fout = open('/local/bandwidth-test.log')
cmd = 'iperf -s -p 5002 -e -t 20 -f MBytes'
proc = subprocess.Popen(cmd, stdout=fout)

proc.communicate()
fout.close()