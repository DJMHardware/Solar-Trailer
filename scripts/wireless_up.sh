#!/bin/sh
iptables -t nat -D POSTROUTING -o enx0c5b8f279a64 -j MASQUERADE
iptables -D FORWARD -i enx0c5b8f279a64 -o br0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -D FORWARD -i br0 -o enx0c5b8f279a64 -j ACCEPT
route del default
dhclient wlx04d4c464c21f
iptables -t nat -A POSTROUTING -o wlx04d4c464c21f -j MASQUERADE
iptables -A FORWARD -i wlx04d4c464c21f -o br0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i br0 -o wlx04d4c464c21f -j ACCEPT
route -n
