#! /usr/bin/python3

from pubsub import pub
import meshtastic
import meshtastic.serial_interface
import time
import datetime
import threading
import sys
from socket import *
import traceback 
import select

# TODO: allow fromId None in nodeTable
# An exception occurred: 'shortName'
# Traceback (most recent call last):
#   File "/home/greg/src/python/meshtastic/meshaprs/igate.py", line 122, in onReceive
# KeyError: 'shortName'
# Packet: {'from': 862350356, 'to': 4294967295, 'decoded': {'portnum': 'POSITION_APP', 'payload': b'\r\x00\xc0s\x1c\x15\x00\xc0L\xb7\x18\x83\x01%\x85\xe8;f\xb8\x01\x11', 'position': {'latitudeI': 477347840, 'longitudeI': -1219706880, 'altitude': 131, 'time': 1715202181, 'precisionBits': 17, 'raw': latitude_i: 477347840
# longitude_i: -1219706880
# altitude: 131
# time: 1715202181
# precision_bits: 17
# , 'latitude': 47.734784, 'longitude': -121.970688}}, 'id': 87452024, 'rxTime': 1715202170, 'rxSnr': -9.5, 'hopLimit': 6, 'rxRssi': -121, 'hopStart': 7, 'raw': from: 862350356
# to: 4294967295
# decoded {
#   portnum: POSITION_APP
#   payload: "\r\000\300s\034\025\000\300L\267\030\203\001%\205\350;f\270\001\021"
# }
# id: 87452024
# rx_time: 1715202170
# rx_snr: -9.5
# hop_limit: 6
# rx_rssi: -121
# hop_start: 7
# , 'fromId': None, 'toId': '^all'}

interface = None
spin = True
identTimer = None
messageTable = {}
nodeTable = {}
neighborTable = {}
encryptedTable = []
aprsTable = {}
gatewayId = 'N/A'
sock = None
serverHost = 'northwest.aprs2.net'
serverPort = 14578
callSign = 'your_callsign'
callPass = 'your_callsign_pass_code'
version = '0.0.8'
aprsISConected = False


def onConnectionEstablished(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
  print ('Connected to Meshtastic device')

def onConnectionLost(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    global spin
    print ('Disconnected from Meshtastic device')
    spin = False

def onReceive(packet, interface): # called when a packet arrives
    global nodeTable
    global gatewayId

    try:
        hopLimit = packet['hopLimit'] if 'hopLimit' in packet else 0
        hopStart = packet['hopStart'] if 'hopStart' in packet else hopLimit

        insertIntoNodeTable(packet['from'], packet['fromId'], packet)
        nodeTable[packet['from']]['hopLimit'] = hopLimit
        nodeTable[packet['from']]['hopStart'] = hopStart
        nodeTable[packet['from']]['hops'] = hopStart - hopLimit

        # skip encrypted packets as they cannot be decoded (easily)
        if 'encrypted' in packet:
            print('\n{}: Skipping encrypted packet fromId: {} - {} - {} to {} on channel {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])) if 'rxTime' in packet else 'N/A',
                packet['fromId'] if packet['fromId'] != None else 'N/A',
                nodeTable[packet['from']]['longName'] if packet['from'] != None and packet['from'] in nodeTable else 'N/A',
                nodeTable[packet['from']]['shortName'] if packet['from'] != None and packet['from'] in nodeTable else 'N/A',
                packet['toId'],
                packet['channel']
                )
            )
            insertIntoEncryptedTable(packet['rxTime'], packet['fromId'], packet['from'], packet['toId'], packet['to'], packet['channel'])
            return

        print('\n{}: {}: {} - {} - {} - {} => {} on channel {} with {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])) if 'rxTime' in packet else 'N/A',
            packet['decoded']['portnum'],
            packet['from'],
            packet['fromId'] if packet['fromId'] != None else 'N/A',
            nodeTable[packet['from']]['shortName'] if packet['from'] != None and packet['from'] in nodeTable else 'N/A',
            nodeTable[packet['from']]['longName']  if packet['from'] != None and packet['from'] in nodeTable else 'N/A',
            packet['toId'],
            packet['channel'] if 'channel' in packet else 'N/A',
            nodeTable[packet['from']]['hwModel'] if packet['from'] != None and packet['from'] in nodeTable else 'N/A'
            )
        )

        if packet['decoded']['portnum'] == 'TELEMETRY_APP':
            if 'deviceMetrics' in packet['decoded']['telemetry']:
                print('{}: TELEMETRY_APP: batteryLevel: {}, voltage: {}, channelUtilization: {}, airUtilTx: {}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                    dictValueOrDefault('batteryLevel', packet['decoded']['telemetry']['deviceMetrics']),
                    dictValueOrDefault('voltage', packet['decoded']['telemetry']['deviceMetrics']),
                    dictValueOrDefault('channelUtilization', packet['decoded']['telemetry']['deviceMetrics']),
                    dictValueOrDefault('airUtilTx', packet['decoded']['telemetry']['deviceMetrics'])
                    )
                )
            elif 'environmentMetrics' in packet['decoded']['telemetry']:
                print('{}: TELEMETRY_APP: temperature: {}, relativeHumidity: {}, barometricPressure: {}, gasResistance: {}, iaq: {}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                    dictValueOrDefault('temperature', packet['decoded']['telemetry']['environmentMetrics']),
                    dictValueOrDefault('relativeHumidity', packet['decoded']['telemetry']['environmentMetrics']),
                    dictValueOrDefault('barometricPressure', packet['decoded']['telemetry']['environmentMetrics']),
                    dictValueOrDefault('gasResistance', packet['decoded']['telemetry']['environmentMetrics']),
                    dictValueOrDefault('iaq', packet['decoded']['telemetry']['environmentMetrics'])
                    )
                )
            else:
                print('{}: TELEMETRY_APP: unknown payload\n{}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                    packet
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
                dictValueOrDefault('id', packet['decoded']['user']),
                dictValueOrDefault('longName', packet['decoded']['user']),
                dictValueOrDefault('shortName', packet['decoded']['user']),
                dictValueOrDefault('macaddr', packet['decoded']['user']),
                dictValueOrDefault('hwModel', packet['decoded']['user']),
                dictValueOrDefault('wantResponse', packet['decoded'])
                )
            )

        elif packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
            print('{}: TEXT_MESSAGE_APP: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['text']
                )
            )

            # someday... convert to APRS format and write APRS message packet to APRS-IS?

            # if packet is dm to this node send appropriate response
            channel = 0
            if gatewayId == packet['toId'] or '^all' == packet['toId']:
                direct = False if '^all' == packet['toId'] else True
                destId = '^all' if '^all' == packet['toId'] else packet['fromId']

                if direct == False and 'channel' in packet:
                    channel = packet['channel']

                response = handleRfCommand(packet['decoded']['text'], direct)
                if response != None:
                    interface.sendText(response, destinationId = destId, wantAck = False, channelIndex = channel)

            insertIntoMessageTable(
                packet['rxTime'],
                packet['fromId'] if packet['fromId'] != None else 'N/A',
                packet['toId'],
                channel,
                packet['rxSnr'],
                packet['rxRssi'],
                packet['hopLimit'],
                packet['decoded']['text']
            )

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
                dictValueOrDefault('rxSnr', packet),
                dictValueOrDefault('hopLimit', packet),
                dictValueOrDefault('rxRssi', packet)
                )
            )

        elif packet['decoded']['portnum'] == 'NEIGHBORINFO_APP':
            print('{}: NEIGHBORINFO_APP: rxSnr: {}, hopLimit: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['rxSnr'] if 'rxSnr' in packet else 'N/A',
                packet['hopLimit']
                )
            )

            insertIntoNeighborTable(packet)

        elif packet['decoded']['portnum'] == 'RANGE_TEST_APP':
            print('{}: RANGE_TEST_APP: payload: {}, rxSnr: {}, rxRssi: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['payload'].decode('ascii'),
                dictValueOrDefault('rxSnr', packet),
                dictValueOrDefault('rxRssi', packet)
                )
            )

        elif packet['decoded']['portnum'] == 'ADMIN_APP':
            print('{}: ADMIN_APP: payload: {}, admin: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['payload'].decode('ascii'),
                packet['decoded']['admin']
                )
            )

        else:
            print('{}: UNKNOWN {}:'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum']
                )
            )
            print('packet: {}'.format(packet))

        print('{}: {}: id: {}, rxTime: {}, hopLimit: {}, hopStart: {}, hops: {}, rxSnr: {}, rxRssi: {}, priority: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            dictValueOrDefault('portnum', packet['decoded']),
            dictValueOrDefault('id', packet),
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            hopLimit,
            dictValueOrDefault('hopStart', packet),
            hopStart - hopLimit,
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
    global aprsISConected
    global callSign

    if packet['from'] != None and packet['from'] in nodeTable and 'latitude' in packet['decoded']['position'] and 'longitude' in packet['decoded']['position']:
        lat_aprs, lon_aprs = decimal_degrees_to_aprs(packet['decoded']['position']['latitude'], packet['decoded']['position']['longitude'])

        # aprsPacket = 'MESH{}>APRS,qAR,{}:!{}/{}nMeshtastic {} ({}, {})'.format(
        aprsPacket = 'MESH{}>APRS,qAR,{}:!{}\{}oMeshtastic {} ({}, {})'.format(
            nodeTable[packet['from']]['shortName'].upper(),
            callSign,
            lat_aprs,
            lon_aprs,
            packet['fromId'],
            nodeTable[packet['from']]['longName'],
            nodeTable[packet['from']]['hwModel']
            )

        for i in range(connectRetry):
            # check for sock disconnect and try to reconnect before sending APRS
            if sock == None or aprsISConected == False:
                print('Could not send to APRS-IS; sock == None and/or aprsISConected == False (pre). Attempting to reconnect...')
                serverHost = 'northwest.aprs2.net'
                serverPort = 14578
                if False == connectAndLoginToAprsIs():
                    print('ERROR: could not log into APRS-IS server: {} port {}'.format(serverHost, serverPort))
                    time.sleep(3)
                    continue

            try:
                sock.send((aprsPacket + '\n').encode())
                print(aprsPacket)
                insertIntoAprsTable(packet['from'], packet['rxTime'])
                return
            except Exception as e:
                aprsISConected = False
                print('An exception occurred: {}'.format(e))
    else:
        print('No fromId, latitude, longitude or not in nodeTable!!!\n{}'.format(packet))

def connectAndLoginToAprsIs(connectRetry = 3):
    global sock
    global version
    global aprsISConected
    global serverHost
    global serverPort
    global callSign
    global callPass

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
            try:
                sock.shutdown(0)
            except Exception as e:
                pass

            sock.close()
            sock = None

        try:
            sock = socket(AF_INET, SOCK_STREAM)
            sock.connect((serverHost, serverPort))

            time.sleep(1)
            login = 'user {} pass {} vers "KD7UBJ Meshtastic APRS/MQTT iGate v{}" \n'.format(callSign, callPass, version)
            sock.send(login.encode())
            time.sleep(1)
            data = sock.recv(1024)

            if ('# logresp {} verified').format(callSign).encode() in data:
                sock.settimeout(1)
                aprsISConected = True
                return True
            else:
                print('Did not receive login verification.')
                aprsISConected = False
                if sock != None:
                    sock.shutdown(0)
                    sock.close()
                    sock = None
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()

    try:
        sock.shutdown(0)
    except Exception as e:
        pass

    sock.close()
    sock = None

    return False

def handleRfCommand(message, direct):
    global version
    global gatewayId

    if 'about' == message.lower():
        print('Received "about": {}'.format(message))
        return 'KD7UBJ Meshtastic APRS/MQTT iGate ({}) v{}. Send "commands" to list services.'.format(gatewayId, version)
    elif 'commands' == message.lower():
        print('Received "commands": {}'.format(message))
        return '"about" this iGate. "commands" to list possible commands. "git" link to this server\'s python source code. "ping" to receive pong'
    elif 'git' == message.lower():
        print('Received "git": {}'.format(message))
        return 'https://github.com/GregEigsti/meshaprs'
    elif 'ping' == message.lower():
        print('Received "ping": {}'.format(message))
        return 'pong'
    else:
        print('Received unknown command: {}'.format(message))
        if direct:
            return 'Unknown command: {}. Send "commands" to list services.'.format(message)

    return None

def insertIntoMessageTable(rxTime, fromId, toId, channel, rxSnr, rxRssi, hopLimit, text):
    global messageTable
    messageTable[rxTime] = { 'fromId': fromId, 'toId': toId, 'channel': channel, 'rxSnr': rxSnr, 'rxRssi': rxRssi, 'hopLimit': hopLimit, 'text': text }

def insertIntoNodeTable(_from, fromId, data):
    global nodeTable

    newDict = {}
    newDict['fromId'] = fromId
    newDict['hopsAway'] = 'N/A'
    newDict['hopLimit'] = 'N/A'
    newDict['hopStart'] = 'N/A'
    newDict['hops'] = 'N/A'

    if _from in nodeTable:
        newDict = nodeTable[_from]

    for key in data:
        # TODO: add decoded dict?
        # print('===> data[{}]: {}, {}'.format(key, data[key], type(data[key])))
        if not isinstance(data[key], dict) and not isinstance(data[key], meshtastic.mesh_pb2.MeshPacket) and not key in ['from', 'to', 'priority', 'toId', 'raw', 'id']:
            newDict[key] = data[key]

    nodeTable[_from] = newDict

    # print('--------------------------------------------------------------------------------')
    # print('{} {}'.format(_from, nodeTable[_from]))
    # print('--------------------------------------------------------------------------------')

def insertIntoEncryptedTable(rxTime, fromId, _from, toId, to, channel):
    global encryptedTable
    encryptedTable.append([rxTime, fromId, _from, toId, to, channel])

def insertIntoAprsTable(_from, rxTime):
    global aprsTable

    count = 1
    if _from in aprsTable:
        count = aprsTable[_from]['count'] + 1
    aprsTable[_from] = { 'rxTime': rxTime, 'count': count }

def insertIntoNeighborTable(packet):
    global neighborTable
    global nodeTable

    temp = {}
    if packet['from'] in neighborTable:
        temp = neighborTable[packet['from']]

    for node in packet['decoded']['neighborinfo']['neighbors']:
        temp[node['nodeId']] = { 'rxTime': packet['rxTime'], 'snr': node['snr'] }

    neighborTable[packet['from']] = temp

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

def getMyNodeInfo():
    global interface
    global gatewayId

    thisNode = interface.getMyNodeInfo()

    print('\n=== Base Node ================================================================================')
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
    
    print('==============================================================================================')

def displayMessages():
    global messageTable
    global nodeTable

    print('\n==============================================================================================\n{} messages received:'.format(len(messageTable)))

    try:
        for key in messageTable:
            print("{}: {} - {} - {}, toId: {}, channel: {}, rxSnr: {}, rxRssi: {}, hopLimit: {}, hops: {}, text: {}".format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(key)),
                messageTable[key]['fromId'],
                nodeTable[messageTable[key]['from']]['shortName'] if messageTable[key]['fromId'] in nodeTable else 'N/A',
                nodeTable[messageTable[key]['from']]['longName']  if messageTable[key]['fromId'] in nodeTable else 'N/A',
                messageTable[key]['toId'],
                messageTable[key]['channel'],
                messageTable[key]['rxSnr'],
                messageTable[key]['rxRssi'],
                messageTable[key]['hopLimit'],
                nodeTable[messageTable[key]['from']]['hops'],
                messageTable[key]['text']
                )
            )
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('==============================================================================================')

def displayEncrypted():
    global encryptedTable
    global nodeTable

    print('\n==============================================================================================\n{} encrypted items:'.format(len(encryptedTable)))

    try:
        for message in encryptedTable:
            print('{:19s}: {:9s} - {:4s} - {:36s}, from: {:10s}, toId: {:4s}, to: {:10d}, channel: {:3d}, hops: {:1s}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(message[0])),
                message[1] if message[1] != None else 'N/A',
                nodeTable[message[2]]['shortName'] if message[0] != None and message[2] in nodeTable else 'N/A',
                nodeTable[message[2]]['longName'] if message[0] != None and message[2] in nodeTable else 'N/A',
                str(message[2]) if message[2] != None else 'N/A',
                message[3],
                message[4],
                message[5],
                str(nodeTable[message[2]]['hops'])
                )
            )
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('==============================================================================================')

def displayAprs():
    global aprsTable
    global nodeTable

    print('\n==============================================================================================\n{} APRS participants:'.format(len(aprsTable)))

    try:
        for key in aprsTable:
            print("{:19s}: {:9s} - {:4s} - {:36s}, count: {:3d}, hwModel: {:23s}, hops: {:1s}".format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(aprsTable[key]['rxTime'])),
                nodeTable[key]['fromId'],
                nodeTable[key]['shortName'],
                nodeTable[key]['longName'],
                aprsTable[key]['count'],
                nodeTable[key]['hwModel'],
                str(nodeTable[key]['hops'])
                )
            )
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('==============================================================================================')

def displayNeighbors():
    global neighborTable
    global nodeTable

    print('\n==============================================================================================\n{} Node(s) Reporting Neighbors'.format(len(neighborTable)))

    try:
        for keyFrom in neighborTable:
            print('--- {} - {} - {} - {} has {} neighbors'.format(
                keyFrom,
                nodeTable[keyFrom]['fromId'],
                nodeTable[keyFrom]['shortName'],
                nodeTable[keyFrom]['longName'],
                len(neighborTable[keyFrom])
                )
            )

            for key in neighborTable[keyFrom]:
                print("{:10d} - {:9s} - {:4s} - {:36s}, rxTime: {}, snr: {:2.2f}, hops: {:1s}".format(
                    key,
                    nodeTable[key]['fromId'],
                    nodeTable[key]['shortName'],
                    nodeTable[key]['longName'],
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(neighborTable[keyFrom][key]['rxTime'])),
                    neighborTable[keyFrom][key]['snr'],
                    str(nodeTable[key]['hops'])
                    )
                )
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('==============================================================================================')

def displayNodes():
    global interface
    global nodeTable

    try:
        nodes = interface.nodes.values()
        print('\n==============================================================================================\n{} nodes seen:'.format(len(nodes)))

        # for node in (sorted(interface.nodes.values(), key = lambda d: d['lastHeard'], reverse = True)):
        for node in nodes:

            insertIntoNodeTable(node['num'], node['user']['id'], node['user'])

            if 'hopsAway' in node:
                nodeTable[node['num']]['hopsAway'] = node['hopsAway']
                if nodeTable[node['num']]['hops'] == 'N/A':
                    nodeTable[node['num']]['hops'] = node['hopsAway']
            
            print("{} - {} - {} - {}, macaddr: {}, hwModel: {}, role: {}, lat: {}, lon: {}, alt: {}, time: {}, lastHeard: {}, hopsAway: {}, hopLimit: {}, hopStart: {}, hops: {}".format(
                node['user']['id'],
                node['user']['shortName'],
                node['user']['longName'],
                node['num'],
                node['user']['macaddr'],
                node['user']['hwModel'],
                node['user']['role'] if 'role' in node['user'] else 'N/A',
                node['position']['latitude'] if 'position' in node and 'latitude' in node['position'] else 'N/A',
                node['position']['longitude'] if 'position' in node and 'longitude' in node['position'] else 'N/A',
                node['position']['altitude'] if 'position' in node and 'altitude' in node['position'] else 'N/A',
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node['position']['time'])) if 'position' in node and 'time' in node['position'] else 'N/A',
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node['lastHeard'])) if 'lastHeard' in node else 'N/A',
                nodeTable[node['num']]['hopsAway'],
                nodeTable[node['num']]['hopLimit'],
                nodeTable[node['num']]['hopStart'],
                nodeTable[node['num']]['hops']
                )
            )

        print('==============================================================================================')
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

def broadcastIdent(createTimer = True):
    global interface
    global version
    global gatewayId
    global identTimer

    ident = 'KD7UBJ Meshtastic APRS/MQTT iGate ({}) v{}. Send "commands" to list services. https://discord.gg/5KUHrjbZ'.format(gatewayId, version)
    print('\n{} Broadcasting Ident: {}'.format(datetime.datetime.now(), ident))
    interface.sendText(ident, destinationId = '^all', wantAck = False)

    if createTimer:
        identTimer = threading.Timer(60 * 60 * 12, broadcastIdent)
        identTimer.start()

# sb 0 this is a test broadcast message to channel 0
# sb 1 this is a test broadcast message to channel 1
def sendBroadcastMessage(command):
    global interface

    print('\n==============================================================================================\nsend broadcast message:')

    try:
        print(command)
        parts = command.split()
        print('count   : {}'.format(len(parts))) # 4
        print('ch-index: {}'.format(parts[1]))
        print('message : {}'.format(" ".join(parts[2:])))

        retVal = interface.sendText(" ".join(parts[2:]), destinationId = '^all', channelIndex = int(parts[1]), wantAck = True)
        print(retVal)
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('==============================================================================================')

# sd !10a37e85 this is a direct message to !10a37e85
def sendDirectMessage(command):
    global interface

    print('\n==============================================================================================\nsend direct message:')

    try:
        print(command)
        parts = command.split()
        print('count  : {}'.format(len(parts))) # 4
        print('to     : {}'.format(parts[1]))
        print('message: {}'.format(" ".join(parts[2:])))

        retVal = interface.sendText(" ".join(parts[2:]), destinationId = parts[1], wantAck = True)
        print(retVal)
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('==============================================================================================')

def dictValueOrDefault(key, parent, default = 'N/A'):
    return parent[key] if key in parent else default

def pollKeyboard():
    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        line = sys.stdin.readline()
        if line:
            return line

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
    global spin

    if command == None:
        return

    if command.lower().startswith('a'):
        displayAprs()
    elif command.lower().startswith('c'):
        printKbdCommands()
    elif command.lower().startswith('e'):
        displayEncrypted()
    elif command.lower().startswith('i'):
        print('\n==============================================================================================\nbroadcast ident:')
        broadcastIdent(createTimer = False)
        print('==============================================================================================')
    elif command.lower().startswith('m'):
        displayMessages()
    elif command.lower().startswith('nt'):
        displayNodes()
    elif command.lower().startswith('n'):
        displayNeighbors()
    elif command.lower().startswith('q'):
        print('Quitting...')
        spin = False
    elif command.lower().startswith('sb'):
        sendBroadcastMessage(command)
    elif command.lower().startswith('sd'):
        sendDirectMessage(command)
    else:
        print('Unknown keyboard command')

def printKbdCommands():
    print('\n==============================================================================================\nkeyboard commands:')
    print('a  => show APRS participants sent to the APRS-IS')
    print('c  => show available commands')
    print('e  => show nodes using encryption')
    print('i  => broadcast ident')
    print('m  => show received messages')
    print('n  => show neighbors')
    print('nt => show nodes table')
    print('q  => quit')
    # sb 0 this is a test broadcast message to channel 0
    print('sb <ch-index> <message> => send broadcast message')
    # sd !10a37e85 this is a direct message to !10a37e85
    print('sd <to> <message> => send direct message')
    print('==============================================================================================')

def main():
    global interface
    global spin
    global sock
    global identTimer


    # log in to APRS-IS server with passcode to allow writing
    # serverHost = 'first.aprs.net'
    # serverPort = 10152
    serverHost = 'northwest.aprs2.net'
    serverPort = 14578
    if False == connectAndLoginToAprsIs():
        print('ERROR: could not log into APRS-IS server: {} port {}'.format(serverHost, serverPort))

    print('Finding Meshtastic device')
    interface = meshtastic.serial_interface.SerialInterface()

    pub.subscribe(onConnectionEstablished, 'meshtastic.connection.established')
    pub.subscribe(onConnectionLost, 'meshtastic.connection.lost')

    time.sleep(2)
    getMyNodeInfo()
    displayNodes()
    printKbdCommands()

    pub.subscribe(onReceive, 'meshtastic.receive')

    # broadcastIdent(createTimer = True)

    while (spin == True):
        workSleep(.5)

    if None != identTimer:
        identTimer.cancel()

    interface.close()
    if sock != None:
        sock.shutdown(0)
        sock.close()

    print('Exiting...')

if __name__=='__main__':
    main()
