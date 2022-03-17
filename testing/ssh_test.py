from pexpect import pxssh
import sys
import time
import re

try:
    s = pxssh.pxssh()
    print(s.login("switch.emulab-experiment.emulab-net.emulab.net", "cabart", port="22",ssh_key="/home/cabart/.ssh/id_ed25519",sync_multiplier=2))
except pxssh.ExceptionPxssh as e:
    print("pxssh failed on login:",e)
    sys.exit(1)


print("login worked")

print("test uptime of switch:")
#s.sendline("uptime")
s.sendline("nohup python /local/bt-cc-model-code-main/switch/queueMeasurements.py &")
pidPattern = re.compile("\[[0-9]+\] [0-9]+")
s.prompt()
response = s.before.decode("utf-8")
print(response)
pidExtended = pidPattern.findall(response)[0]
number = re.compile("[0-9]+")
pid = number.findall(pidExtended)[1]
print("pid",pid)

time.sleep(5)
s.sendline("pgrep -af python")
s.prompt()
response = s.before.decode("utf-8")
print(response)

s.sendline("kill -SIGTERM " + pid)
s.prompt()
response = s.before.decode("utf-8")
print(response)

s.logout()