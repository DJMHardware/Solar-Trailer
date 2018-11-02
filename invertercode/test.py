import time
import serial
import paho.mqtt.client as mqtt

# ser = serial.Serial("/dev/ttyUSB3", 19200, timeout=0.1)


def mqtt_on_message(client, userdata, message):
    topic = message.topic.split('/')
    print ('topic = ' + str(topic[1]))
    print ('message received = ' + message.payload)


client = mqtt.Client('Inverter_py')
client.connect('localhost')
client.loop_start()
client.subscribe(("Remote/+", 0))
client.on_message = mqtt_on_message
while True:
    time.sleep(0.1)




#while True:
#    ser.write('hello')
ser = serial.Serial("/dev/ttyUSB1", baudrate=9600,
                    bytesize=8, parity='E', stopbits=1, timeout=0.1)
print (ser.rts)
#ser.rts = False
print (ser.rts)
#while True:
#    ser.write('hello')
print (ser.rts)
#ser.rts = True
ser.write(':0322F00F\n')
while True:
    ser.write(':0322F00F\n')
    x = ser.read_until()
    print (x)
