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

interface = None
spin = True
identTimer = None
gatewayId = 'N/A'
version = '0.0.10'


class Helpers:
    def formatNodeString(self, _from, fromId, shortName, longName):
        return '{:9s} - {:4s} - {:36s} - {:10s}'.format(
            fromId if fromId != None else 'N/A',
            shortName if shortName != None else 'N/A',
            longName if longName != None else 'N/A',
            _from if _from != None else 'N/A'
        )

class Nodes(Helpers):
    global interface
    nodeTable = {}

    def insert(self, _from, fromId, data):
        newDict = {}
        newDict['fromId'] = fromId
        newDict['hopsAway'] = 'N/A'
        newDict['hopLimit'] = 'N/A'
        newDict['hopStart'] = 'N/A'
        newDict['hops'] = 'N/A'

        if _from in self.nodeTable:
            newDict = self.nodeTable[_from]

        for key in data:
            if not isinstance(data[key], dict) and not isinstance(data[key], meshtastic.mesh_pb2.MeshPacket) and not key in ['from', 'to', 'priority', 'toId', 'raw', 'id']:
                newDict[key] = data[key]

        self.nodeTable[_from] = newDict

    def get(self):
        return self.nodeTable

    def display(self):
        print('\n==============================================================================================\n{} nodes seen:'.format(len(self.nodeTable)))
        try:
            nodesHeard = interface.nodes.values()
            for node in nodesHeard:
                self.insert(node['num'], node['user']['id'], node['user'])

                if 'hopsAway' in node:
                    self.nodeTable[node['num']]['hopsAway'] = node['hopsAway']
                    if self.nodeTable[node['num']]['hops'] == 'N/A':
                        self.nodeTable[node['num']]['hops'] = node['hopsAway']

                nodeString = formatNodeString(
                    str(node['num']),
                    node['user']['id'],
                    node['user']['shortName'],
                    node['user']['longName']
                )

                print("{}, macaddr: {}, hwModel: {}, role: {}, lat: {}, lon: {}, alt: {}, time: {}, lastHeard: {}, hopsAway: {}, hopLimit: {}, hopStart: {}, hops: {}".format(
                    nodeString,
                    node['user']['macaddr'],
                    node['user']['hwModel'],
                    node['user']['role'] if 'role' in node['user'] else 'N/A',
                    node['position']['latitude'] if 'position' in node and 'latitude' in node['position'] else 'N/A',
                    node['position']['longitude'] if 'position' in node and 'longitude' in node['position'] else 'N/A',
                    node['position']['altitude'] if 'position' in node and 'altitude' in node['position'] else 'N/A',
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node['position']['time'])) if 'position' in node and 'time' in node['position'] else 'N/A',
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node['lastHeard'])) if 'lastHeard' in node else 'N/A',
                    self.nodeTable[node['num']]['hopsAway'],
                    self.nodeTable[node['num']]['hopLimit'],
                    self.nodeTable[node['num']]['hopStart'],
                    self.nodeTable[node['num']]['hops']
                    )
                )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
        print('==============================================================================================')

class Neighbors(Helpers):
    neighborTable = {}

    def insert(self, packet):
        temp = {}
        if packet['from'] in self.neighborTable:
            temp = self.neighborTable[packet['from']]

        for node in packet['decoded']['neighborinfo']['neighbors']:
            temp[node['nodeId']] = { 'rxTime': packet['rxTime'], 'snr': node['snr'] }

        self.neighborTable[packet['from']] = temp

    def get(self):
        return self.neighborTable

    def display(self):
        print('\n==============================================================================================\n{} Node(s) Reporting Neighbors:'.format(len(self.neighborTable)))
        try:
            for keyFrom in self.neighborTable:
                nodeString = formatNodeString(
                    str(keyFrom),
                    nodes.get()[keyFrom]['fromId'],
                    nodes.get()[keyFrom]['shortName'],
                    nodes.get()[keyFrom]['longName']
                )

                print('--- {} has {} neighbors'.format(
                    nodeString,
                    len(self.neighborTable[keyFrom])
                    )
                )

                for key in self.neighborTable[keyFrom]:
                    nodeString = formatNodeString(
                        str(key),
                        nodes.get()[key]['fromId'],
                        nodes.get()[key]['shortName'],
                        nodes.get()[key]['longName']
                    )

                    print("{}, rxTime: {}, snr: {:2.2f}, hops: {:1s}".format(
                        nodeString,
                        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.neighborTable[keyFrom][key]['rxTime'])),
                        self.neighborTable[keyFrom][key]['snr'],
                        str(nodes.get()[key]['hops'])
                        )
                    )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
        print('==============================================================================================')

class Messages(Helpers):
    messageTable = []

    def insert(self, _from, rxTime, fromId, toId, channel, rxSnr, rxRssi, text):
        self.messageTable.append([ _from, rxTime, fromId, toId, channel, rxSnr, rxRssi, text ])

    def get(self):
        return self.messageTable

    def display(self):
        print('\n==============================================================================================\n{} Messages Received:'.format(len(self.messageTable)))
        try:
            for message in self.messageTable:
                nodeString = formatNodeString(
                    str(message[0]),
                    message[2],
                    nodes.get()[message[0]]['shortName'] if message[0] in nodes.get() and 'shortName' in nodes.get()[message[0]] else 'N/A',
                    nodes.get()[message[0]]['longName'] if message[0] in nodes.get() and 'longName' in nodes.get()[message[0]] else 'N/A'
                )

                print("{}: {}, toId: {}, channel: {}, rxSnr: {}, rxRssi: {}, hopLimit: {}, hops: {}, text: {}".format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(message[1])),
                    nodeString,
                    message[3],
                    message[4],
                    message[5],
                    message[6],
                    nodes.get()[message[0]]['hopLimit'] if message[0] in nodes.get() and 'hopLimit' in nodes.get()[message[0]] else 'N/A',
                    nodes.get()[message[0]]['hops'] if message[0] in nodes.get() and 'hops' in nodes.get()[message[0]] else 'N/A',
                    message[7]
                    )
                )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
        print('==============================================================================================')

class Encrypted(Helpers):
    encryptedTable = []

    def insert(self, rxTime, fromId, _from, toId, to, channel):
        self.encryptedTable.append([rxTime, fromId, _from, toId, to, channel])

    def get(self):
        return self.encryptedTable

    def display(self):
        print('\n==============================================================================================\n{} encrypted items:'.format(len(self.encryptedTable)))
        try:
            for message in self.encryptedTable:
                nodeString = formatNodeString(
                    str(message[2]) if message[2] != None else 'N/A',
                    message[1] if message[1] != None else 'N/A',
                    nodes.get()[message[2]]['shortName'] if message[0] != None and message[2] in nodes.get() else 'N/A',
                    nodes.get()[message[2]]['longName'] if message[0] != None and message[2] in nodes.get() else 'N/A'
                )

                print('{:19s}: {}, toId: {:4s}, to: {:10d}, channel: {:3d}, hops: {:1s}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(message[0])),
                    nodeString,
                    message[3],
                    message[4],
                    message[5],
                    str(nodes.get()[message[2]]['hops'])
                    )
                )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
        print('==============================================================================================')

class Aprs(Helpers):
    aprsTable = {}
    aprsISConected = False
    callSign = 'your_callsign'
    callPass = 'your_callsign_pass_code'
    # log in to APRS-IS server with passcode to allow writing
    # serverHost = 'first.aprs.net'
    # serverPort = 10152
    serverHost = 'northwest.aprs2.net'
    serverPort = 14578
    sock = None

    def insert(self, _from, rxTime):
        count = 1
        if _from in self.aprsTable:
            count = self.aprsTable[_from]['count'] + 1
        self.aprsTable[_from] = { 'rxTime': rxTime, 'count': count }

    def get(self):
        return self.aprsTable

    def display(self):
        print('\n==============================================================================================\n{} APRS participants:'.format(len(self.aprsTable)))
        try:
            for key in self.aprsTable:
                nodeString = formatNodeString(
                    str(key),
                    nodes.get()[key]['fromId'],
                    nodes.get()[key]['shortName'],
                    nodes.get()[key]['longName']
                )

                print("{:19s}: {}, count: {:3d}, hwModel: {:23s}, hops: {:1s}".format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.aprsTable[key]['rxTime'])),
                    nodeString,
                    self.aprsTable[key]['count'],
                    nodes.get()[key]['hwModel'],
                    str(nodes.get()[key]['hops'])
                    )
                )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
        print('==============================================================================================')

    def decimalDegreesToAprs(self, latitude, longitude):
        lat_deg = int(abs(latitude))
        lat_min = (abs(latitude) - lat_deg) * 60
        lon_deg = int(abs(longitude))
        lon_min = (abs(longitude) - lon_deg) * 60

        lat_dir = 'N' if latitude >= 0 else 'S'
        lon_dir = 'E' if longitude >= 0 else 'W'

        lat_aprs = "{:02d}{:05.2f}{}".format(lat_deg, lat_min, lat_dir)
        lon_aprs = "{:03d}{:05.2f}{}".format(lon_deg, lon_min, lon_dir)

        return lat_aprs, lon_aprs

    def connectAndLoginToAprsIs(self, connectRetry = 3):
        # http://www.aprs.org/doc/APRS101.PDF
        # http://www.aprs.org/APRS-docs/PROTOCOL.TXT
        # http://www.aprs.org/symbols/symbols-new.txt
        # !DDMM.hhN/DDDMM.hhW$...    POSIT ( no APRS)
        # =DDMM.hhN/DDDMM.hhW$...    POSIT (APRS message capable)

        if self.sock != None and self.aprsISConected == True:
            return True

        for i in range(connectRetry):
            print('Connect and log in to APRS-IS server attempt {}: {} port {}'.format(i + 1, self.serverHost, self.serverPort))

            if self.sock != None:
                try:
                    self.sock.shutdown(0)
                except Exception as e:
                    pass

                self.sock.close()
                self.sock = None

            try:
                self.sock = socket(AF_INET, SOCK_STREAM)
                self.sock.connect((self.serverHost, self.serverPort))

                time.sleep(1)
                login = 'user {} pass {} vers "KD7UBJ Meshtastic APRS/MQTT iGate v{}" \n'.format(self.callSign, self.callPass, version)
                self.sock.send(login.encode())
                time.sleep(1)
                data = self.sock.recv(1024)

                if ('# logresp {} verified').format(self.callSign).encode() in data:
                    self.sock.settimeout(1)
                    self.aprsISConected = True
                    return True
                else:
                    print('Did not receive login verification.')
                    self.aprsISConected = False
                    if self.sock != None:
                        self.sock.shutdown(0)
                        self.sock.close()
                        self.sock = None
            except Exception as e:
                print('An exception occurred: {}'.format(e))
                traceback.print_exc()

        try:
            self.sock.shutdown(0)
        except Exception as e:
            pass

        print('ERROR: could not log into APRS-IS server: {} port {}'.format(self.serverHost, self.serverPort))
        self.sock.close()
        self.sock = None

        return False

    def sendToAprsIs(self, packet, connectRetry = 3):
        if packet['from'] != None and packet['from'] in nodes.get() and 'latitude' in packet['decoded']['position'] and 'longitude' in packet['decoded']['position'] and 'shortName' in nodes.get()[packet['from']] and 'longName' in nodes.get()[packet['from']] and 'hwModel' in nodes.get()[packet['from']] and packet['fromId'] != None:
            lat_aprs, lon_aprs = aprs.decimalDegreesToAprs(packet['decoded']['position']['latitude'], packet['decoded']['position']['longitude'])

            # aprsPacket = 'MESH{}>APRS,qAR,{}:!{}/{}nMeshtastic {} ({}, {})'.format(
            aprsPacket = 'MESH{}>APRS,qAR,{}:!{}\{}oMeshtastic {} ({}, {})'.format(
                nodes.get()[packet['from']]['shortName'].upper(),
                self.callSign,
                lat_aprs,
                lon_aprs,
                packet['fromId'],
                nodes.get()[packet['from']]['longName'],
                nodes.get()[packet['from']]['hwModel']
                )

            for i in range(connectRetry):
                # check for sock disconnect and try to reconnect before sending APRS
                if self.sock == None or self.aprsISConected == False:
                    print('Could not send to APRS-IS; sock == None and/or aprsISConected == False (pre). Attempting to reconnect...')
                    if False == self.connectAndLoginToAprsIs():
                        print('ERROR: could not log into APRS-IS server: {} port {}'.format(self.serverHost, self.serverPort))
                        time.sleep(3)
                        continue

                try:
                    self.sock.send((aprsPacket + '\n').encode())
                    print(aprsPacket)
                    aprs.insert(packet['from'], packet['rxTime'])
                    return
                except Exception as e:
                    self.aprsISConected = False
                    print('An exception occurred: {}'.format(e))
        else:
            print('Missing required field for APS packet generation\n{}'.format(packet))

    def recv(self, size):
        try:
            return self.sock.recv(size)
        except Exception:
            return None

    def shutdown(self):
        if self.sock != None:
            self.sock.shutdown(0)
            self.sock.close()

nodes = Nodes()
neighbors = Neighbors()
messages = Messages()
aprs = Aprs()
encrypted = Encrypted()


def onConnectionEstablished(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
  print ('Connected to Meshtastic device')

def onConnectionLost(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    global spin
    print ('Disconnected from Meshtastic device')
    spin = False

def formatNodeString(_from, fromId, shortName, longName):
    return '{:9s} - {:4s} - {:36s} - {:10s}'.format(
        fromId if fromId != None else 'N/A',
        shortName if shortName != None else 'N/A',
        longName if longName != None else 'N/A',
        _from if _from != None else 'N/A'
    )

def onReceive(packet, interface): # called when a packet arrives
    global gatewayId

    try:
        hopLimit = packet['hopLimit'] if 'hopLimit' in packet else 0
        hopStart = packet['hopStart'] if 'hopStart' in packet else hopLimit

        nodes.insert(packet['from'], packet['fromId'], packet)

        nodes.get()[packet['from']]['hopLimit'] = hopLimit
        nodes.get()[packet['from']]['hopStart'] = hopStart
        nodes.get()[packet['from']]['hops'] = hopStart - hopLimit

        # skip encrypted packets as they cannot be decoded (easily)
        if 'encrypted' in packet:
            print('\n{}: Skipping encrypted packet fromId: {} - {} - {} to {} on channel {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])) if 'rxTime' in packet else 'N/A',
                packet['fromId'] if packet['fromId'] != None else 'N/A',
                nodes.get()[packet['from']]['longName'] if packet['from'] != None and packet['from'] in nodes.get() and 'longName' in nodes.get()[packet['from']] else 'N/A',
                nodes.get()[packet['from']]['shortName'] if packet['from'] != None and packet['from'] in nodes.get() and 'longName' in nodes.get()[packet['from']] else 'N/A',
                packet['toId'],
                packet['channel']
                )
            )
            encrypted.insert(packet['rxTime'], packet['fromId'], packet['from'], packet['toId'], packet['to'], packet['channel'])
            return

        nodeString = formatNodeString(
            str(packet['from']),
            packet['fromId'] if packet['fromId'] != None else 'N/A',
            nodes.get()[packet['from']]['shortName'] if packet['from'] != None and packet['from'] in nodes.get() and 'shortName' in nodes.get()[packet['from']] else 'N/A',
            nodes.get()[packet['from']]['longName']  if packet['from'] != None and packet['from'] in nodes.get()  and 'longName' in nodes.get()[packet['from']] else 'N/A'
        )

        print('\n{}: {:16s}: {} => {} on channel {} with {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])) if 'rxTime' in packet else 'N/A',
            packet['decoded']['portnum'],
            nodeString,
            packet['toId'],
            packet['channel'] if 'channel' in packet else 'N/A',
            nodes.get()[packet['from']]['hwModel'] if packet['from'] != None and packet['from'] in nodes.get() and 'hwModel' in nodes.get()[packet['from']] else 'N/A'
            )
        )

        if packet['decoded']['portnum'] == 'TELEMETRY_APP':
            if 'deviceMetrics' in packet['decoded']['telemetry']:
                print('{}: {:16s}: batteryLevel: {}, voltage: {}, channelUtilization: {}, airUtilTx: {}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                    packet['decoded']['portnum'],
                    dictValueOrDefault('batteryLevel', packet['decoded']['telemetry']['deviceMetrics']),
                    dictValueOrDefault('voltage', packet['decoded']['telemetry']['deviceMetrics']),
                    dictValueOrDefault('channelUtilization', packet['decoded']['telemetry']['deviceMetrics']),
                    dictValueOrDefault('airUtilTx', packet['decoded']['telemetry']['deviceMetrics'])
                    )
                )
            elif 'environmentMetrics' in packet['decoded']['telemetry']:
                print('{}: {:16s}: temperature: {}, relativeHumidity: {}, barometricPressure: {}, gasResistance: {}, iaq: {}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                    packet['decoded']['portnum'],
                    dictValueOrDefault('temperature', packet['decoded']['telemetry']['environmentMetrics']),
                    dictValueOrDefault('relativeHumidity', packet['decoded']['telemetry']['environmentMetrics']),
                    dictValueOrDefault('barometricPressure', packet['decoded']['telemetry']['environmentMetrics']),
                    dictValueOrDefault('gasResistance', packet['decoded']['telemetry']['environmentMetrics']),
                    dictValueOrDefault('iaq', packet['decoded']['telemetry']['environmentMetrics'])
                    )
                )
            else:
                print('{}: {:16s}: unknown payload\n{}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                    packet['decoded']['portnum'],
                    packet
                    )
                )

        elif packet['decoded']['portnum'] == 'POSITION_APP':
            print('{}: {:16s}: latitude: {}, longitude: {}, altitude: {}, time: {}, satsInView: {}, precisionBits: {}, PDOP: {}, groundTrack: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum'],
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

            aprs.sendToAprsIs(packet)

        elif packet['decoded']['portnum'] == 'NODEINFO_APP':
            print('{}: {:16s}: id: {}, longName: {}, shortName: {}, macaddr: {}, hwModel: {}, wantResponse: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum'],
                dictValueOrDefault('id', packet['decoded']['user']),
                dictValueOrDefault('longName', packet['decoded']['user']),
                dictValueOrDefault('shortName', packet['decoded']['user']),
                dictValueOrDefault('macaddr', packet['decoded']['user']),
                dictValueOrDefault('hwModel', packet['decoded']['user']),
                dictValueOrDefault('wantResponse', packet['decoded'])
                )
            )

        elif packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
            print('{}: {:16s}: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum'],
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

            messages.insert(
                packet['from'],
                packet['rxTime'],
                packet['fromId'] if packet['fromId'] != None else 'N/A',
                packet['toId'],
                channel,
                packet['rxSnr'],
                packet['rxRssi'],
                packet['decoded']['text']
            )

        elif packet['decoded']['portnum'] == 'TRACEROUTE_APP':
            print('{}: {:16s}: rxSnr: {}, hopLimit: {}, wantAck: {}, rxRssi: {}, hopStart: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum'],
                packet['rxSnr'],
                packet['hopLimit'],
                packet['wantAck'],
                packet['rxRssi'],
                packet['hopStart']
                )
            )

        elif packet['decoded']['portnum'] == 'ROUTING_APP':
            print('{}: {:16s}: rxSnr: {}, hopLimit: {}, rxRssi: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum'],
                dictValueOrDefault('rxSnr', packet),
                dictValueOrDefault('hopLimit', packet),
                dictValueOrDefault('rxRssi', packet)
                )
            )

        elif packet['decoded']['portnum'] == 'NEIGHBORINFO_APP':
            print('{}: {:16s}: rxSnr: {}, hopLimit: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum'],
                packet['rxSnr'] if 'rxSnr' in packet else 'N/A',
                packet['hopLimit']
                )
            )

            neighbors.insert(packet)

        elif packet['decoded']['portnum'] == 'RANGE_TEST_APP':
            print('{}: {:16s}: payload: {}, rxSnr: {}, rxRssi: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum'],
                packet['decoded']['payload'].decode('ascii'),
                dictValueOrDefault('rxSnr', packet),
                dictValueOrDefault('rxRssi', packet)
                )
            )

        elif packet['decoded']['portnum'] == 'ADMIN_APP':
            print('{}: {:16s}: payload: {}, admin: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['portnum'],
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

        print('{}: {:16s}: id: {}, rxTime: {}, rxSnr: {}, rxRssi: {}, priority: {}, hopLimit: {}, hopStart: {}, hops: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            dictValueOrDefault('portnum', packet['decoded']),
            dictValueOrDefault('id', packet),
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            dictValueOrDefault('rxSnr', packet),
            dictValueOrDefault('rxRssi', packet),
            dictValueOrDefault('priority', packet),
            hopLimit,
            dictValueOrDefault('hopStart', packet),
            hopStart - hopLimit
            )
        )

    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()
        print('Packet: {}'.format(packet))

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

def getMyNodeInfo():
    global interface
    global gatewayId

    print('\n=== Base Node ================================================================================')
    thisNode = interface.getMyNodeInfo()
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
    for i in range (0, int(seconds * 10)):
        handleKeyboardCommand(pollKeyboard())
        aprs.recv(1024)
        time.sleep(0.1)

def handleKeyboardCommand(command):
    global interface
    global spin

    if command == None:
        return
    elif command.lower().startswith('a'):
        aprs.display()
    elif command.lower().startswith('c'):
        printKbdCommands()
    elif command.lower().startswith('e'):
        encrypted.display()
    elif command.lower().startswith('i'):
        print('\n==============================================================================================\nbroadcast ident:')
        broadcastIdent(createTimer = False)
        print('==============================================================================================')
    elif command.lower().startswith('m'):
        messages.display()
    elif command.lower().startswith('nt'):
        nodes.display()
    elif command.lower().startswith('n'):
        neighbors.display()
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
    global identTimer

    aprs.connectAndLoginToAprsIs()

    print('Finding Meshtastic device')
    interface = meshtastic.serial_interface.SerialInterface()

    pub.subscribe(onConnectionEstablished, 'meshtastic.connection.established')
    pub.subscribe(onConnectionLost, 'meshtastic.connection.lost')

    time.sleep(2)
    getMyNodeInfo()
    nodes.display()
    printKbdCommands()

    pub.subscribe(onReceive, 'meshtastic.receive')

    # broadcastIdent(createTimer = True)

    while (spin == True):
        workSleep(.5)

    if None != identTimer:
        identTimer.cancel()

    interface.close()
    aprs.shutdown()

    print('Exiting...')

if __name__=='__main__':
    main()
