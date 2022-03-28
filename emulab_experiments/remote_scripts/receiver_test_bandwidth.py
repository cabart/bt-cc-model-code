import subprocess

fout = open('/local/bandwidth-test.log','w')
cmd = 'iperf -s -p 5002 -e -t 20 -f m'
proc = subprocess.Popen(cmd.split(), stdout=fout)

proc.communicate()
fout.close()