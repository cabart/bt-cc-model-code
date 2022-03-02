from pexpect import pxssh

try:
    s = pxssh.pxssh()
    print(s.login("node1.emulab-experiment.emulab-net.emulab.net", "cabart", port="22",ssh_key="/home/cabart/.ssh/id_ed25519"))
except pxssh.ExceptionPxssh as e:
    print("pxssh failed on login:",e)

try:
    #ss = pxssh.pxssh(timeout=10)
    ss = pxssh.pxssh()
    #print(ss.login("node2.emulab-experiment.emulab-net.emulab.net", "cabart", port="28002",ssh_key="/home/cabart/.ssh/id_ed25519"))
    ss.login("pc606.emulab.net","cabart",port="26874",ssh_key="/home/cabart/.ssh/id_ed25519")
except pxssh.ExceptionPxssh as e:
    print("pxssh failed on login:",e)

print("login worked")

print("test uptime of machine 1:")
s.sendline("uptime")
s.prompt()
response = s.before.decode("utf-8")
print(response)

print("test uptime of machine 2:")
ss.sendline("uptime") # causes error for some reason?
ss.prompt()
response2 = ss.before.decode("utf-8")
print(response2)

s.logout()
ss.logout()