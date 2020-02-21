#!/bin/sh
# redirect all output into a logfile
exec 1>> /tmp/test.log 2>&1

case "$1" in
wlan0)
    case "$2" in
    CONNECTED)
        # do stuff on connect with wlan0
        echo wlan0 connected
        ;;
    DISCONNECTED)
        # do stuff on disconnect with wlan0
        echo wlan0 disconnected
        ;;
    *)
        >&2 echo empty or undefined event for wlan0: "$2"
        exit 1
        ;;
    esac
    ;;

wlx04d4c464c21f)
    case "$2" in
    CONNECTED)
        # do stuff on connect with wlan1
        echo wlx04d4c464c21f connected
	(/sbin/route del default 2> /dev/null || true)
	/sbin/dhclient -r wlx04d4c464c21f
	/sbin/dhclient wlx04d4c464c21f
	/usr/sbin/iptables-restore < /etc/iptables/rules-wifi.v4
        ;;
    DISCONNECTED)
        # do stuff on disconnect with wlan1
        echo wlx04d4c464c21f disconnected
        (/sbin/route del default 2> /dev/null || true)
        /sbin/dhclient -r enx0c5b8f279a64
        /sbin/dhclient enx0c5b8f279a64
        /usr/sbin/iptables-restore < /etc/iptables/rules-cell.v4

        ;;
    *)
        >&2 echo empty or undefined event for wlan1: "$2"
        exit 1
        ;;
    esac
    ;;

*)
    >&2 echo empty or undefined interface: "$1"
    exit 1
    ;;
esac
