sudo tc qdisc add dev $1 root handle 5:0 htb default 1
sudo tc class add dev $1 parent 5:0 classid 5:1 htb rate 500Mbit burst 15k
sudo tc qdisc add dev $1 parent 5:1 handle 10: netem delay 1ms limit 100