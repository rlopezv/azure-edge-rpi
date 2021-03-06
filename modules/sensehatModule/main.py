import random
import time
import sys
import threading
import uuid
import iothub_client
from sense_hat import SenseHat
import datetime
import json
# pylint: disable=E0611
from iothub_client import IoTHubModuleClient, IoTHubClientError, IoTHubTransportProvider
from iothub_client import IoTHubMessage, IoTHubMessageDispositionResult, IoTHubError, DeviceMethodReturnValue

# messageTimeout - the maximum time in milliseconds until a message times out.
# The timeout period starts at IoTHubModuleClient.send_event_async.
# By default, messages do not expire.
MESSAGE_TIMEOUT = 10000

#Message sample rate in seconds
MESSAGE_SAMPLE = 10

RED = (255, 0, 0)
GREEN = (0,255,0)
BLUE = (0,0,255)


# global counters
RECEIVE_CONTEXT = 0
RECEIVE_CALLBACKS = 0
SEND_CALLBACKS = 0
SEND_SENSEHAT_CALLBACKS = 0

DEVICE_CLIENT_RESPONSE = ""
DEVICE_MESSAGE_TIMEOUT = 10000
DEVICE_METHOD_TIMEOUT = 60
DEVICE_METHOD_USER_CONTEXT = 42
DEVICE_METHOD_NAME = "e2e_device_method_name"
DEVICE_METHOD_PAYLOAD = "\"I'm a happy little string for python E2E test\""
DEVICE_METHOD_RESPONSE_PREFIX = "e2e_test_response-"
DEVICE_METHOD_EVENT = threading.Event()
DEVICE_METHOD_CALLBACK_COUNTER = 0


# Recover from context
DEVICE_ID= "g5-iotedge-rpi"
# Choose HTTP, AMQP or MQTT as transport protocol.  Currently only MQTT is supported.
PROTOCOL = IoTHubTransportProvider.MQTT

#Message sending status
sense = SenseHat()
messageSending = True

# read sense hat and send
def read_and_send_measurements_from_sensehat(hubManager):
    global SEND_SENSEHAT_CALLBACKS
    sense.clear(BLUE)  # passing in an RGB tuple
    temperature = sense.get_temperature()
    temperature_h = sense.get_temperature_from_humidity()
    temperature_p = sense.get_temperature_from_pressure()
    humidity = sense.get_humidity()
    pressure = sense.get_pressure()
    timeCreated = datetime.datetime.utcnow().isoformat()
    MSG_TXT = "{\"deviceId\":\"%s\",\"temperature\": %.2f,\"temperature_h\": %.2f,\"temperature_p\": %.2f,\"humidity\": %.2f,\"pressure\": %.2f,\"deviceTime\": \"%s\"}"
    msg_txt_formatted = MSG_TXT % (DEVICE_ID,temperature, temperature_h, temperature_p, humidity, pressure, timeCreated)
    message = IoTHubMessage(msg_txt_formatted)
    hubManager.forward_event_to_output("output2", message, 0)
    SEND_SENSEHAT_CALLBACKS += 1
    sense.clear()
    print ( "    Total messages sent: %d" % SEND_SENSEHAT_CALLBACKS )

# Callback received when the message that we're forwarding is processed.
def send_confirmation_callback(message, result, user_context):
    global SEND_CALLBACKS
    print ( "Confirmation[%d] received for message with result = %s" % (user_context, result) )
    map_properties = message.properties()
    key_value_pair = map_properties.get_internals()
    print ( "    Properties: %s" % key_value_pair )
    SEND_CALLBACKS += 1
    print ( "    Total calls confirmed: %d" % SEND_CALLBACKS )

# receive_message_callback is invoked when an incoming message arrives on the specified 
# input queue (in the case of this sample, "input1").  Because this is a filter module, 
# we will forward this message onto the "output1" queue.
def receive_message_callback(message, hubManager):
    global RECEIVE_CALLBACKS
    message_buffer = message.get_bytearray()
    sense.clear(GREEN)
    size = len(message_buffer)
    print ( "    Data: <<<%s>>> & Size=%d" % (message_buffer[:size].decode('utf-8'), size) )
    map_properties = message.properties()
    key_value_pair = map_properties.get_internals()
    print ( "    Properties: %s" % key_value_pair )
    RECEIVE_CALLBACKS += 1
    print ( "    Total calls received: %d" % RECEIVE_CALLBACKS )
    hubManager.forward_event_to_output("output1", message, 0)
    return IoTHubMessageDispositionResult.ACCEPTED


# This function will be called every time a method request is received
def method_callback(method_name, payload, user_context):
    global messageSending
    global sense
    print('received method call:')
    print('\tmethod name:', method_name)
    print('\tpayload:', str(payload))
    if "start" == method_name:
        print('\tStarting sendind measures')
        messageSending = True
    elif "stop" == method_name:
        print('\tStoping sendind measures')
        messageSending = False
    elif "alert" == method_name:
        print('\tAlert recieved')
        sense.show_message("Alert")
    else:
        print('\tUnknown method')    
    retval = DeviceMethodReturnValue()
    retval.status = 200
    retval.response = "{\"Message received\":\"value\"}"
    return retval

class HubManager(object):

    def __init__(
            self,
            protocol=IoTHubTransportProvider.MQTT):
        self.client_protocol = protocol
        self.client = IoTHubModuleClient()
        self.client.create_from_environment(protocol)
        # set the time until a message times out
        self.client.set_option("messageTimeout", MESSAGE_TIMEOUT)
        
        # sets the callback when a message arrives on "input1" queue.  Messages sent to 
        # other inputs or to the default will be silently discarded.
        self.client.set_message_callback("input1", receive_message_callback, self)
        print('subscribing to method calls')
        # Register the callback with the client
        self.client.set_module_method_callback(method_callback, 0)
    # Forwards the message received onto the next stage in the process.
    def forward_event_to_output(self, outputQueueName, event, send_context):
        self.client.send_event_async(
            outputQueueName, event, send_confirmation_callback, send_context)

def main(protocol):
    try:
        print ( "\nPython %s\n" % sys.version )
        print ( "IoT Hub Client" )

        hub_manager = HubManager(protocol)
        print ( "Starting the IoT Hub using protocol %s..." % hub_manager.client_protocol )
        print ( "Now waiting for messages and will indefinitely.  Press Ctrl-C to exit. ")

        while True:
            if messageSending:
                read_and_send_measurements_from_sensehat(hub_manager)
            time.sleep(MESSAGE_SAMPLE)

    except IoTHubError as iothub_error:
        print ( "Unexpected error %s from IoTHub" % iothub_error )
        return
    except KeyboardInterrupt:
        print ( "IoTHub stopped" )

if __name__ == '__main__':
    main(PROTOCOL)