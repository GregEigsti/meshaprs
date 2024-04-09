#! /usr/bin/python3

#
# Credit to datagod and his MeshWatch project for providing an example/starting-point for this project
# https://meshtastic.discourse.group/t/meshwatch-testing-and-monitoring-tool/3923
# https://github.com/datagod/meshwatch
#

from pubsub import pub
import meshtastic
import meshtastic.serial_interface
import time
from signal import signal, SIGINT
import sys
from sys import exit
from socket import *
import traceback 
import select

interface = None
spin = True
nodeTable = {}
encryptedTable = {}
gatewayId = ''
sock = None
callSign = 'your_callsign'
callPass = 'your_callsign_pass_code'
version = '0.0.1'
aprsISConected = False


def onConnectionEstablished(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
  print ('onConnectionEstablished')

def onConnectionLost(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    global spin
    print ('onConnectionLost')
    spin = False

def onReceive(packet, interface): # called when a packet arrives
    global nodeTable
    global gatewayId

    try:
        # skip encrypted packets as they cannot be decoded (easily)
        if 'encrypted' in packet:
            print('\nSkipping encrypted packet from {} ({}) to {}'.format(hex(int(packet['id'])), packet['id'], packet['toId']))
            insertIntoEncryptedTable(packet['from'], packet['to'], packet['channel'])
            return

        # print from / to line
        print('\n{}: {}: {} => {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            packet['decoded']['portnum'],
            packet['fromId'] if packet['fromId'] != None else 'N/A',
            packet['toId']))

        if packet['decoded']['portnum'] == 'TELEMETRY_APP':
            print('{}: TELEMETRY_APP: batteryLevel: {}, voltage: {}, channelUtilization: {}, airUtilTx: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                dictValueOrDefault('batteryLevel', packet['decoded']['telemetry']['deviceMetrics']),
                dictValueOrDefault('voltage', packet['decoded']['telemetry']['deviceMetrics']),
                dictValueOrDefault('channelUtilization', packet['decoded']['telemetry']['deviceMetrics']),
                dictValueOrDefault('airUtilTx', packet['decoded']['telemetry']['deviceMetrics'])
                )
            )

        elif packet['decoded']['portnum'] == 'POSITION_APP':
            print('{}: POSITION_APP: latitude: {}, longitude: {}, altitude: {}, time: {}, satsInView: {}, precisionBits: {}, PDOP: {}, groundTrack: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                dictValueOrDefault('latitude', packet['decoded']['position']),
                dictValueOrDefault('longitude', packet['decoded']['position']),
                dictValueOrDefault('altitude', packet['decoded']['position']),
                dictValueOrDefault('time', packet['decoded']['position']),
                dictValueOrDefault('satsInView', packet['decoded']['position']),
                dictValueOrDefault('precisionBits', packet['decoded']['position']),
                dictValueOrDefault('PDOP', packet['decoded']['position']),
                dictValueOrDefault('groundTrack', packet['decoded']['position'])
                )
            )

            # send APRS packet to APRS-IS
            sendToAprsIs(packet)

        elif packet['decoded']['portnum'] == 'NODEINFO_APP':
            print('{}: NODEINFO_APP: id: {}, longName: {}, shortName: {}, macaddr: {}, hwModel: {}, wantResponse: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                dictValueOrDefault('wantResponse', packet['decoded']),
                dictValueOrDefault('id', packet['decoded']['user']),
                dictValueOrDefault('longName', packet['decoded']['user']),
                dictValueOrDefault('shortName', packet['decoded']['user']),
                dictValueOrDefault('macaddr', packet['decoded']['user']),
                dictValueOrDefault('hwModel', packet['decoded']['user'])
                )
            )

            insertIntoNodeTable(
                packet['decoded']['user']['id'],
                packet['decoded']['user']['longName'],
                packet['decoded']['user']['shortName'],
                packet['decoded']['user']['hwModel'])
            
        elif packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
            print('{}: TEXT_MESSAGE_APP: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['text']
                )
            )

            # someday... convert to APRS format and write APRS packet to APRS-IS?

            # if packet is dm to this node send appropriate response
            if gatewayId == packet['toId']:
                response = handleRfCommand(packet['decoded']['text'])
                interface.sendText(response, destinationId=packet['fromId'], wantAck = False)

        elif packet['decoded']['portnum'] == 'TRACEROUTE_APP':
            print('{}: TRACEROUTE_APP: rxSnr: {}, hopLimit: {}, wantAck: {}, rxRssi: {}, hopStart: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['rxSnr'],
                packet['hopLimit'],
                packet['wantAck'],
                packet['rxRssi'],
                packet['hopStart']
                )
            )

        elif packet['decoded']['portnum'] == 'ROUTING_APP':
            print('{}: ROUTING_APP: rxSnr: {}, hopLimit: {}, rxRssi: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['rxSnr'],
                packet['hopLimit'],
                packet['rxRssi']
                )
            )

        elif packet['decoded']['portnum'] == 'NEIGHBORINFO_APP':
            print('{}: NEIGHBORINFO_APP: rxSnr: {}, hopLimit: {}, rxRssi: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['rxSnr'],
                packet['hopLimit'],
                packet['rxRssi']
                )
            )

        else:
            print('{}: UNKNOWN {}:'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum']
                )
            )
            print('packet: {}'.format(packet))

        print('{}: {}: id: {}, rxTime: {}, hopLimit: {}, rxSnr: {}, rxRssi: {}, priority: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            dictValueOrDefault('portnum', packet['decoded']),
            dictValueOrDefault('id', packet),
            # dictValueOrDefault('rxTime', packet),
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            dictValueOrDefault('hopLimit', packet),
            dictValueOrDefault('rxSnr', packet),
            dictValueOrDefault('rxRssi', packet),
            dictValueOrDefault('priority', packet)
            )
        )

    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()
        print('Packet: {}'.format(packet))

def sendToAprsIs(packet, connectRetry = 3):
    global nodeTable
    global sock
    global callSign
    global aprsISConected

    if packet['fromId'] != None and packet['fromId'] in nodeTable and 'latitude' in packet['decoded']['position'] and 'longitude' in packet['decoded']['position']:
        lat_aprs, lon_aprs = decimal_degrees_to_aprs(packet['decoded']['position']['latitude'], packet['decoded']['position']['longitude'])

        aprsPacket = 'MESH{}>APRS,qAR,{}:!{}/{}/Meshtastic {} ({}, {})'.format(
            nodeTable[packet['fromId']]['shortName'],
            callSign,
            lat_aprs,
            lon_aprs,
            packet['fromId'],
            nodeTable[packet['fromId']]['longName'],
            nodeTable[packet['fromId']]['hwModel']
            )

        for i in range(connectRetry):
            # check for sock disconnect and try to reconnect before sending APRS
            if sock == None or aprsISConected == False:
                print('Could not send to APRS-IS; sock == None and/or aprsISConected == False (pre). Attempting to reconnect...')
                serverHost = 'northwest.aprs2.net'
                serverPort = 14578
                if False == connectAndLoginToAprsIs(serverHost, serverPort, callSign, callPass):
                    print('ERROR: could not log into APRS-IS server: {} port {}'.format(serverHost, serverPort))
                    time.sleep(3)
                    continue

            try:
                sock.send((aprsPacket + '\n').encode())
                print(aprsPacket)
                return
            except Exception as e:
                aprsISConected = False
                print('An exception occurred: {}'.format(e))
    else:
        print('No fromId, latitude, longitude or not in nodeTable!!!\n{}'.format(packet))

def connectAndLoginToAprsIs(serverHost, serverPort, callSign, callPass, connectRetry = 3):
    global sock
    global version
    global aprsISConected

    # http://www.aprs.org/doc/APRS101.PDF
    # http://www.aprs.org/APRS-docs/PROTOCOL.TXT
    # http://www.aprs.org/symbols/symbols-new.txt
    # !DDMM.hhN/DDDMM.hhW$...    POSIT ( no APRS)
    # =DDMM.hhN/DDDMM.hhW$...    POSIT (APRS message capable)

    if sock != None and aprsISConected == True:
        return True

    for i in range(connectRetry):
        print('Connect and log in to APRS-IS server attempt {}: {} port {}'.format(i + 1, serverHost, serverPort))

        if sock != None:
            # sock.shutdown(0)
            sock.close()

        sock = socket(AF_INET, SOCK_STREAM)
        # TODO: what happens if connect fails? Handle it...
        sock.connect((serverHost, serverPort))
        time.sleep(1)
        login = 'user {} pass {} vers "KD7UBJ Meshtastic iGate v{}" \n'.format(callSign, callPass, version)
        sock.send(login.encode())
        time.sleep(1)
        data = sock.recv(1024)

        if ('# logresp {} verified').format(callSign).encode() in data:
            sock.settimeout(1)
            aprsISConected = True
            return True
        else:
            aprsISConected = False
            if sock != None:
                sock.shutdown(0)
                sock.close()
                sock = None

    return False

def handleRfCommand(message):
    if 'about' in message.lower():
        print('Received "about": {}'.format(message))
        return 'KD7UBJ Meshtastic iGate v{}. Send "commands" to list services.'.format(version)
    elif 'commands' in message.lower():
        print('Received "commands": {}'.format(message))
        return '"about" this iGate. "commands" to list possible commands. "ping" to receive pong'
    elif 'ping' in message.lower():
        print('Received "ping": {}'.format(message))
        return 'pong'
    else:
        print('Received unknown command: {}'.format(message))
        return 'Unknown command: {}. Send "commands" to list services.'.format(message)

def insertIntoNodeTable(id, longName, shortName, hwModel):
    global nodeTable

    nodeTable[id] = { 'longName': longName, 'shortName': shortName, 'hwModel': hwModel }

def insertIntoEncryptedTable(_from, to, channel):
    global encryptedTable
    
    encryptedTable[_from] = { 'to': to, 'channel': channel }

def decimal_degrees_to_aprs(latitude, longitude):
    lat_deg = int(abs(latitude))
    lat_min = (abs(latitude) - lat_deg) * 60
    lon_deg = int(abs(longitude))
    lon_min = (abs(longitude) - lon_deg) * 60
    
    lat_dir = 'N' if latitude >= 0 else 'S'
    lon_dir = 'E' if longitude >= 0 else 'W'
    
    lat_aprs = "{:02d}{:05.2f}{}".format(lat_deg, lat_min, lat_dir)
    lon_aprs = "{:03d}{:05.2f}{}".format(lon_deg, lon_min, lon_dir)
    
    return lat_aprs, lon_aprs

def getMyNodeInfo(interface):
    global gatewayId

    thisNode = interface.getMyNodeInfo()
    # DecodePacket('MYNODE',thisNode,'','',PrintSleep =PrintSleep)

    print('=== Base Node =================================')
    gatewayId = dictValueOrDefault('id', thisNode['user'])
    print('id: {}, longName: {}, shortName: {}, hwModel: {}, macaddr: {}, batteryLevel: {}, voltage: {}, channelUtilization: {}, airUtilTx: {}, lat: {}, lon: {}, altitude: {}'.format(
        gatewayId,
        dictValueOrDefault('longName', thisNode['user']),
        dictValueOrDefault('shortName', thisNode['user']),
        dictValueOrDefault('hwModel', thisNode['user']),
        dictValueOrDefault('macaddr', thisNode['user']),
        dictValueOrDefault('batteryLevel', thisNode['deviceMetrics']),
        dictValueOrDefault('voltage', thisNode['deviceMetrics']),
        dictValueOrDefault('channelUtilization', thisNode['deviceMetrics']),
        dictValueOrDefault('airUtilTx', thisNode['deviceMetrics']),
        dictValueOrDefault('latitude', thisNode['position']),
        dictValueOrDefault('longitude', thisNode['position']),
        dictValueOrDefault('altitude', thisNode['position']),
        )
    )
    
    print('===============================================')

def displayNodes(interface):
    global nodeTable

    try:
        for node in (sorted(interface.nodes.values(), key=lambda d: d['lastHeard'], reverse = True)):
            # print('\n{}\n'.format(node))
            print("ID: {} ({}), NAME: {} ({}), MAC: {}, HWMODEL: {}, LAT: {}, LON: {}, ALT: {}, TIME: {}, LAST: {}".format(
                node['user']['id'],
                node['num'],
                node['user']['longName'],
                node['user']['shortName'],
                node['user']['macaddr'],
                node['user']['hwModel'],
                node['position']['latitude'] if 'position' in node and 'latitude' in node['position'] else 'N/A',
                node['position']['longitude'] if 'position' in node and 'longitude' in node['position'] else 'N/A',
                node['position']['altitude'] if 'position' in node and 'altitude' in node['position'] else 'N/A',
                node['position']['time'] if 'position' in node else 'N/A',
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node['lastHeard']))
                )
            )

            insertIntoNodeTable(node['user']['id'], node['user']['longName'], node['user']['shortName'], node['user']['hwModel'])

        print('===============================================')

    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

def dictValueOrDefault(key, parent, default = 'N/A'):
    return parent[key] if key in parent else default

def pollKeyboard():
    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        line = sys.stdin.readline()
        if line:
            return line[0]

    return None

def workSleep(seconds):
    global sock

    for i in range (0, int(seconds * 10)):
        c = pollKeyboard()
        handleKeyboardCommand(c)

        try:
            data = sock.recv(1024)
        except Exception:
        # except socket.timeout:
            continue

        time.sleep(0.1)

def handleKeyboardCommand(command):
    global interface
    global encryptedTable
    global spin

    if command == None:
        return

    if command.lower() == 'q':
        print('Quitting...')
        spin = False
    elif command.lower() == 'n':
        print('\n===============================================\nnodes seen:')
        displayNodes(interface)
    elif command.lower() == 'e':
        print('\n===============================================\nencrypted nodes:')
        # print(encryptedTable)
        try:
            for node in encryptedTable:
                # print('\n{}\n'.format(node))
                print("FROM: {}, TO: {}, CHANNEL: {}".format(
                    node['from'],
                    node['to'],
                    node['channel']
                    )
                )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()

        print('===============================================')
    elif command.lower() == 'c':
        print('\n===============================================\ncommands:')
        print('c => show available commands')
        print('e => show nodes using encryption')
        print('n => show nodes table')
        print('q => quit')
        print('===============================================')

# def SIGINT_handler(signal_received, frame):
#     global spin
#     print('\nSIGINT or CTRL-C detected. Exiting gracefully...')
#     spin = False

def main():
    global interface
    global spin
    global sock
    global callSign
    global callPass

    # signal(SIGINT, SIGINT_handler)

    # log in to APRS-IS server with passcode to allow writing
    # serverHost = 'first.aprs.net'
    # serverPort = 10152
    serverHost = 'northwest.aprs2.net'
    serverPort = 14578
    if False == connectAndLoginToAprsIs(serverHost, serverPort, callSign, callPass):
        print('ERROR: could not log into APRS-IS server: {} port {}'.format(serverHost, serverPort))

    print('Finding Meshtastic device')
    interface = meshtastic.serial_interface.SerialInterface()

    pub.subscribe(onConnectionEstablished, 'meshtastic.connection.established')
    pub.subscribe(onConnectionLost, 'meshtastic.connection.lost')

    time.sleep(2)
    getMyNodeInfo(interface)
    displayNodes(interface)

    pub.subscribe(onReceive, 'meshtastic.receive')

    while (spin == True):
        workSleep(.5)

    interface.close()
    if sock != None:
        sock.shutdown(0)
        sock.close()

    print('Exiting...')

if __name__=='__main__':
    main()

