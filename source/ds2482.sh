#!/bin/sh
sudo modprobe ds2482
sudo sh -c "echo ds2482 0x18 > /sys/bus/i2c/devices/i2c-1/new_device"
# echo 0 > /sys/bus/w1/devices/w1_bus_master1/w1_master_search
