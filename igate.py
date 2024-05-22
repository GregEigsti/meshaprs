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

callSign = 'your_callsign'
callPass = 'your_callsign_pass_code'
version = '0.0.12'

meshaprs = None
nodes = None
neighbors = None
messages = None
aprs = None
encrypted = None
bogotron = None

class Helpers:
    def formatHeaderString(self, packet, nodeString, nodeTable):
        return '{}: {:16s}: {} => {} on channel {} with {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])) if 'rxTime' in packet else 'N/A',
            packet['decoded']['portnum'] if 'decoded' in packet else 'N/A',
            nodeString,
            packet['toId'],
            packet['channel'] if 'channel' in packet else 'N/A',
            nodeTable[packet['from']]['hwModel'] if packet['from'] != None and packet['from'] in nodeTable and 'hwModel' in nodeTable[packet['from']] else 'N/A'
            )

    def formatNodeString(self, _from, fromId, shortName, longName):
        return '{:9s} - {:4s} - {:36s} - {:10s}'.format(
            fromId if fromId != None else 'N/A',
            shortName if shortName != None else 'N/A',
            longName if longName != None else 'N/A',
            _from if _from != None else 'N/A'
        )

    def formatFooterString(self, packet, hopStart, hopLimit):
        return '{}: {:16s}: id: {}, rxTime: {}, rxSnr: {}, rxRssi: {}, priority: {}, hopLimit: {}, hopStart: {}, hops: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            packet['decoded']['portnum'] if 'decoded' in packet else 'N/A',
            self.dictValueOrDefault('id', packet),
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            self.dictValueOrDefault('rxSnr', packet),
            self.dictValueOrDefault('rxRssi', packet),
            self.dictValueOrDefault('priority', packet),
            hopLimit,
            self.dictValueOrDefault('hopStart', packet),
            hopStart - hopLimit
        )

    def dictValueOrDefault(self, key, parent, default = 'N/A'):
        return parent[key] if key in parent else default

class Nodes(Helpers):
    global interface
    nodeTable = {}
    interface = None

    def __init__(self, interface):
        self.interface = interface

    def insert(self, _from, fromId, data):
        newDict = {}
        newDict['fromId'] = fromId
        newDict['hopsAway'] = 'N/A'
        newDict['hopLimit'] = 'N/A'
        newDict['hopStart'] = 'N/A'
        newDict['hops'] = 'N/A'
        newDict['seenCount'] = 0

        if _from in self.nodeTable:
            newDict = self.nodeTable[_from]

        for key in data:
            if not isinstance(data[key], dict) and not isinstance(data[key], meshtastic.mesh_pb2.MeshPacket) and not key in ['from', 'to', 'priority', 'toId', 'raw', 'id']:
                newDict[key] = data[key]

        self.nodeTable[_from] = newDict

    def get(self):
        return self.nodeTable

    def display(self):
        try:
            nodesHeard = self.interface.nodes.values()
            print('\n==============================================================================================\n{} nodes heard:'.format(len(nodesHeard)))
            for node in nodesHeard:
                self.insert(node['num'], node['user']['id'], node['user'])
                self.nodeTable[node['num']]['lastHeard'] = node['lastHeard'] if 'lastHeard' in node else 'N/A'

                if 'hopsAway' in node:
                    self.nodeTable[node['num']]['hopsAway'] = node['hopsAway']
                    if self.nodeTable[node['num']]['hops'] == 'N/A':
                        self.nodeTable[node['num']]['hops'] = node['hopsAway']

                nodeString = self.formatNodeString(
                    str(node['num']),
                    node['user']['id'],
                    node['user']['shortName'],
                    node['user']['longName']
                )

                print('{}, macaddr: {:8s}, hwModel: {:20s}, role: {:13s}, lat: {}, lon: {}, alt: {}, time: {:16s}, lastHeard: {:19s}, hopsAway: {:3s}, hopLimit: {:3s}, hopStart: {:3s}, hops: {:3s}'.format(
                    nodeString,
                    node['user']['macaddr'],
                    node['user']['hwModel'],
                    node['user']['role'] if 'role' in node['user'] else 'N/A',
                    node['position']['latitude'] if 'position' in node and 'latitude' in node['position'] else 'N/A',
                    node['position']['longitude'] if 'position' in node and 'longitude' in node['position'] else 'N/A',
                    node['position']['altitude'] if 'position' in node and 'altitude' in node['position'] else 'N/A',
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node['position']['time'])) if 'position' in node and 'time' in node['position'] else 'N/A',
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node['lastHeard'])) if 'lastHeard' in node and node['lastHeard'] != 'N/A' else 'N/A',
                    str(self.nodeTable[node['num']]['hopsAway']),
                    str(self.nodeTable[node['num']]['hopLimit']),
                    str(self.nodeTable[node['num']]['hopStart']),
                    str(self.nodeTable[node['num']]['hops'])
                    )
                )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
        print('==============================================================================================')

    def displayRecent(self):
        try:
            # nodesHeard = dict(filter(lambda node: (self.nodeTable[node]['seenCount'] > 0), self.nodeTable))
            # print(nodesHeard)
            # An exception occurred: cannot convert dictionary update sequence element #0 to a sequence
            # Traceback (most recent call last):
            # File "/home/greg/src/python/meshtastic/meshaprs/igate.py", line 108, in displayRecent
            #     nodesHeard = dict(filter(lambda node: (self.nodeTable[node]['seenCount'] > 0), self.nodeTable))
            #                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            # TypeError: cannot convert dictionary update sequence element #0 to a sequence

            # print('\n==============================================================================================\n{} nodes heard since start'.format(len(nodesHeard)))
            print('\n==============================================================================================\nnodes heard since start')

            # nodesHeard = self.interface.nodes.values()
            # for node in nodesHeard:
            #     # self.insert(node['num'], node['user']['id'], node['user'])
            #     # TODO: more here?
            #     if self.nodeTable[node['num']]:
            #         self.nodeTable[node['num']]['lastHeard'] = node['lastHeard'] if 'lastHeard' in node else 'N/A'

            # for node in nodesHeard:
            for node in self.nodeTable:
                if self.nodeTable[node]['seenCount'] > 0:
                    nodeString = self.formatNodeString(
                        str(node),
                        self.nodeTable[node]['fromId'] if 'fromId' in self.nodeTable[node] else 'N/A',
                        self.nodeTable[node]['shortName'] if 'shortName' in self.nodeTable[node] else 'N/A',
                        self.nodeTable[node]['longName'] if 'longName' in self.nodeTable[node] else 'N/A'
                    )

                    # TODO: lastHeard is probably stale...

                    print('{}, seenCount: {:4d}, macaddr: {:8s}, hwModel: {:20s}, role: {:13s}, lastHeard: {:19s}, hopsAway: {:3s}, hopLimit: {:3s}, hopStart: {:3s}, hops: {:3s}'.format(
                        nodeString,
                        self.nodeTable[node]['seenCount'] if 'seenCount' in self.nodeTable[node] else 'N/A',
                        self.nodeTable[node]['macaddr'] if 'macaddr' in self.nodeTable[node] else 'N/A',
                        self.nodeTable[node]['hwModel'] if 'hwModel' in self.nodeTable[node] else 'N/A',
                        self.nodeTable[node]['role'] if 'role' in self.nodeTable[node] else 'N/A',
                        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.nodeTable[node]['lastHeard'])) if 'lastHeard' in self.nodeTable[node] and self.nodeTable[node]['lastHeard'] != 'N/A' else 'N/A',
                        str(self.nodeTable[node]['hopsAway']) if 'hopsAway' in self.nodeTable[node] else 'N/A',
                        str(self.nodeTable[node]['hopLimit']) if 'hopLimit' in self.nodeTable[node] else 'N/A',
                        str(self.nodeTable[node]['hopStart']) if 'hopStart' in self.nodeTable[node] else 'N/A',
                        str(self.nodeTable[node]['hops']) if 'hops' in self.nodeTable[node] else 'N/A'
                        )
                    )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
        print('==============================================================================================')

    def getBaseNodeInfo(self):
        print('\n=== Base Node ================================================================================')
        thisNode = self.interface.getMyNodeInfo()
        self.gatewayId = self.dictValueOrDefault('id', thisNode['user'])

        print('id: {}, longName: {}, shortName: {}, hwModel: {}, macaddr: {}, batteryLevel: {}, voltage: {}, channelUtilization: {}, airUtilTx: {}, lat: {}, lon: {}, altitude: {}'.format(
            self.gatewayId,
            self.dictValueOrDefault('longName', thisNode['user']),
            self.dictValueOrDefault('shortName', thisNode['user']),
            self.dictValueOrDefault('hwModel', thisNode['user']),
            self.dictValueOrDefault('macaddr', thisNode['user']),
            self.dictValueOrDefault('batteryLevel', thisNode['deviceMetrics']),
            self.dictValueOrDefault('voltage', thisNode['deviceMetrics']),
            self.dictValueOrDefault('channelUtilization', thisNode['deviceMetrics']),
            self.dictValueOrDefault('airUtilTx', thisNode['deviceMetrics']),
            self.dictValueOrDefault('latitude', thisNode['position']),
            self.dictValueOrDefault('longitude', thisNode['position']),
            self.dictValueOrDefault('altitude', thisNode['position']),
            )
        )
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
            nodeTable = nodes.get()
            for keyFrom in self.neighborTable:
                nodeString = self.formatNodeString(
                    str(keyFrom),
                    nodeTable[keyFrom]['fromId'],
                    nodeTable[keyFrom]['shortName'],
                    nodeTable[keyFrom]['longName']
                )

                print('--- {} has {} neighbors'.format(
                    nodeString,
                    len(self.neighborTable[keyFrom])
                    )
                )

                for key in self.neighborTable[keyFrom]:
                    nodeString = self.formatNodeString(
                        str(key),
                        nodeTable[key]['fromId'] if key in nodeTable and 'fromId' in nodeTable[key] else 'N/A',
                        nodeTable[key]['shortName'] if key in nodeTable and 'shortName' in nodeTable[key] else 'N/A',
                        nodeTable[key]['longName'] if key in nodeTable and 'longName' in nodeTable[key] else 'N/A'
                    )

                    print("{}, rxTime: {}, snr: {:2.2f}, hops: {:1s}".format(
                        nodeString,
                        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.neighborTable[keyFrom][key]['rxTime'])),
                        self.neighborTable[keyFrom][key]['snr'],
                        str(nodeTable[key]['hops'])
                        )
                    )
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
        print('==============================================================================================')

class Bogotron(Helpers):
    bogotronTable = {}

    def insert(self, packet):
        self.bogotronTable[packet['from']] = { 'rxTime': packet['rxTime'] }

    def get(self):
        return self.bogotronTable

    def display(self):
        print('\n==============================================================================================\n{} Bogotrons Seen:'.format(len(self.bogotronTable)))
        try:
            for key in self.bogotronTable:

                # nodeString = self.formatNodeString(
                #     str(key),
                #     nodeTable[key]['fromId'],
                #     nodeTable[key]['shortName'],
                #     nodeTable[key]['longName']
                # )

                print('{:19s}: {}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.bogotronTable[key]['rxTime'])),
                    key
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
            nodeTable = nodes.get()
            for message in self.messageTable:
                nodeString = self.formatNodeString(
                    str(message[0]),
                    message[2],
                    nodeTable[message[0]]['shortName'] if message[0] in nodeTable and 'shortName' in nodeTable[message[0]] else 'N/A',
                    nodeTable[message[0]]['longName'] if message[0] in nodeTable and 'longName' in nodeTable[message[0]] else 'N/A'
                )

                print("{}: {}, toId: {}, channel: {}, rxSnr: {}, rxRssi: {}, hopLimit: {}, hops: {}, text: {}".format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(message[1])),
                    nodeString,
                    message[3],
                    message[4] if message[3] == '^all' else 'N/A',
                    message[5],
                    message[6],
                    nodeTable[message[0]]['hopLimit'] if message[0] in nodeTable and 'hopLimit' in nodeTable[message[0]] else 'N/A',
                    nodeTable[message[0]]['hops'] if message[0] in nodeTable and 'hops' in nodeTable[message[0]] else 'N/A',
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
            nodeTable = nodes.get()
            for message in self.encryptedTable:
                nodeString = self.formatNodeString(
                    str(message[2]) if message[2] != None else 'N/A',
                    message[1] if message[1] != None else 'N/A',
                    nodeTable[message[2]]['shortName'] if message[0] != None and message[2] in nodeTable and 'shortName' in nodeTable[message[2]] else 'N/A',
                    nodeTable[message[2]]['longName'] if message[0] != None and message[2] in nodeTable and 'longName' in nodeTable[message[2]] else 'N/A'
                )

                print('{:19s}: {}, toId: {:4s}, to: {:10d}, channel: {:3d}, hops: {:1s}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(message[0])),
                    nodeString,
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

class Aprs(Helpers):
    aprsTable = {}
    aprsISConected = False
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
            nodeTable = nodes.get()
            for key in self.aprsTable:
                nodeString = self.formatNodeString(
                    str(key),
                    nodeTable[key]['fromId'],
                    nodeTable[key]['shortName'],
                    nodeTable[key]['longName']
                )

                print("{:19s}: {}, count: {:3d}, hwModel: {:23s}, hops: {:1s}".format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.aprsTable[key]['rxTime'])),
                    nodeString,
                    self.aprsTable[key]['count'],
                    nodeTable[key]['hwModel'],
                    str(nodeTable[key]['hops'])
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
                login = 'user {} pass {} vers "KD7UBJ Meshtastic APRS/MQTT iGate v{}" \n'.format(callSign, callPass, version)
                self.sock.send(login.encode())
                time.sleep(1)
                data = self.sock.recv(1024)

                if ('# logresp {} verified').format(callSign).encode() in data:
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
        nodeTable = nodes.get()
        if packet['from'] != None and packet['from'] in nodeTable and 'latitude' in packet['decoded']['position'] and 'longitude' in packet['decoded']['position'] and 'shortName' in nodeTable[packet['from']] and 'longName' in nodeTable[packet['from']] and 'hwModel' in nodeTable[packet['from']] and packet['fromId'] != None:
            lat_aprs, lon_aprs = aprs.decimalDegreesToAprs(packet['decoded']['position']['latitude'], packet['decoded']['position']['longitude'])

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

class MeshAprs(Helpers):
    interface = None
    spin = True
    identTimer = None

    def __init__(self):
        self.interface = meshtastic.serial_interface.SerialInterface()
        pub.subscribe(self.onConnectionEstablished, 'meshtastic.connection.established')
        pub.subscribe(self.onConnectionLost, 'meshtastic.connection.lost')

    def startReceive(self):
        pub.subscribe(self.onReceive, 'meshtastic.receive')

        # self.broadcastIdent(meshaprs.interface, createTimer = True)

        while (self.spin == True):
            self.workSleep(.5, meshaprs.interface)

        if None != self.identTimer:
            self.identTimer.cancel()

    def shutdown(self):
        self.interface.close()

    def onConnectionEstablished(self, interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
        print ('Connected to Meshtastic device')

    def onConnectionLost(self, interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
        print ('Disconnected from Meshtastic device')
        self.spin = False

    def onReceive(self, packet, interface): # called when a packet arrives
        try:
            nodeTable = nodes.get()
            hopLimit = packet['hopLimit'] if 'hopLimit' in packet else 0
            hopStart = packet['hopStart'] if 'hopStart' in packet else hopLimit

            nodes.insert(packet['from'], packet['fromId'], packet)

            if 'fromId' not in packet or packet['fromId'] == None or 'shortName' not in packet or packet['shortName'] == None or 'longName' not in packet or packet['longName'] == None:
                bogotron.insert(packet)

            nodeTable[packet['from']]['hopLimit'] = hopLimit
            nodeTable[packet['from']]['hopStart'] = hopStart
            nodeTable[packet['from']]['hops'] = hopStart - hopLimit
            nodeTable[packet['from']]['seenCount'] = nodeTable[packet['from']]['seenCount'] + 1

            nodeString = self.formatNodeString(
                str(packet['from']),
                packet['fromId'] if packet['fromId'] != None else 'N/A',
                nodeTable[packet['from']]['shortName'] if packet['from'] != None and packet['from'] in nodeTable and 'shortName' in nodeTable[packet['from']] else 'N/A',
                nodeTable[packet['from']]['longName']  if packet['from'] != None and packet['from'] in nodeTable  and 'longName' in nodeTable[packet['from']] else 'N/A'
            )

            headerString = self.formatHeaderString(packet, nodeString, nodeTable)
            print('\n{}'.format(headerString))

            # skip encrypted packets as they cannot be decoded (easily)
            if 'encrypted' in packet:
                print('Encrypted packet.')
                encrypted.insert(packet['rxTime'], packet['fromId'], packet['from'], packet['toId'], packet['to'], packet['channel'])

            elif packet['decoded']['portnum'] == 'TELEMETRY_APP':
                if 'deviceMetrics' in packet['decoded']['telemetry']:
                    print('{}: {:16s}: batteryLevel: {}, voltage: {}, channelUtilization: {}, airUtilTx: {}'.format(
                        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                        packet['decoded']['portnum'],
                        self.dictValueOrDefault('batteryLevel', packet['decoded']['telemetry']['deviceMetrics']),
                        self.dictValueOrDefault('voltage', packet['decoded']['telemetry']['deviceMetrics']),
                        self.dictValueOrDefault('channelUtilization', packet['decoded']['telemetry']['deviceMetrics']),
                        self.dictValueOrDefault('airUtilTx', packet['decoded']['telemetry']['deviceMetrics'])
                        )
                    )
                elif 'environmentMetrics' in packet['decoded']['telemetry']:
                    print('{}: {:16s}: temperature: {}, relativeHumidity: {}, barometricPressure: {}, gasResistance: {}, iaq: {}'.format(
                        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                        packet['decoded']['portnum'],
                        self.dictValueOrDefault('temperature', packet['decoded']['telemetry']['environmentMetrics']),
                        self.dictValueOrDefault('relativeHumidity', packet['decoded']['telemetry']['environmentMetrics']),
                        self.dictValueOrDefault('barometricPressure', packet['decoded']['telemetry']['environmentMetrics']),
                        self.dictValueOrDefault('gasResistance', packet['decoded']['telemetry']['environmentMetrics']),
                        self.dictValueOrDefault('iaq', packet['decoded']['telemetry']['environmentMetrics'])
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
                    self.dictValueOrDefault('latitude', packet['decoded']['position']),
                    self.dictValueOrDefault('longitude', packet['decoded']['position']),
                    self.dictValueOrDefault('altitude', packet['decoded']['position']),
                    self.dictValueOrDefault('time', packet['decoded']['position']),
                    self.dictValueOrDefault('satsInView', packet['decoded']['position']),
                    self.dictValueOrDefault('precisionBits', packet['decoded']['position']),
                    self.dictValueOrDefault('PDOP', packet['decoded']['position']),
                    self.dictValueOrDefault('groundTrack', packet['decoded']['position'])
                    )
                )

                aprs.sendToAprsIs(packet)

            elif packet['decoded']['portnum'] == 'NODEINFO_APP':
                print('{}: {:16s}: id: {}, longName: {}, shortName: {}, macaddr: {}, hwModel: {}, wantResponse: {}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                    packet['decoded']['portnum'],
                    self.dictValueOrDefault('id', packet['decoded']['user']),
                    self.dictValueOrDefault('longName', packet['decoded']['user']),
                    self.dictValueOrDefault('shortName', packet['decoded']['user']),
                    self.dictValueOrDefault('macaddr', packet['decoded']['user']),
                    self.dictValueOrDefault('hwModel', packet['decoded']['user']),
                    self.dictValueOrDefault('wantResponse', packet['decoded'])
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
                if nodes.gatewayId == packet['toId'] or '^all' == packet['toId']:
                    direct = False if '^all' == packet['toId'] else True
                    destId = '^all' if '^all' == packet['toId'] else packet['fromId']

                    if direct == False and 'channel' in packet:
                        channel = packet['channel']

                    response = self.handleRfCommand(packet['decoded']['text'], direct)
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
                    self.dictValueOrDefault('rxSnr', packet),
                    self.dictValueOrDefault('hopLimit', packet),
                    self.dictValueOrDefault('rxRssi', packet)
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
                    self.dictValueOrDefault('rxSnr', packet),
                    self.dictValueOrDefault('rxRssi', packet)
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

            footerString = self.formatFooterString(packet, hopStart, hopLimit)
            print(footerString)
        except Exception as e:
            print('An exception occurred: {}'.format(e))
            traceback.print_exc()
            print('Packet: {}'.format(packet))

    def pollKeyboard(self):
        while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline()
            if line:
                return line

        return None

    def workSleep(self, seconds, interface):
        for i in range (0, int(seconds * 10)):
            self.handleKeyboardCommand(self.pollKeyboard(), interface)
            aprs.recv(1024)
            time.sleep(0.1)

    def handleKeyboardCommand(self, command, interface):
        if command == None:
            return
        elif command.lower().startswith('a'):
            aprs.display()
        elif command.lower().startswith('b'):
            bogotron.display()
        elif command.lower().startswith('c'):
            self.printKbdCommands()
        elif command.lower().startswith('e'):
            encrypted.display()
        elif command.lower().startswith('i'):
            print('\n==============================================================================================\nbroadcast ident:')
            self.broadcastIdent(interface, createTimer = False)
            print('==============================================================================================')
        elif command.lower().startswith('m'):
            messages.display()
        elif command.lower().startswith('nt'):
            nodes.display()
        elif command.lower().startswith('n'):
            neighbors.display()
        elif command.lower().startswith('q'):
            print('Quitting...')
            self.spin = False
        elif command.lower().startswith('r'):
            nodes.displayRecent()
        elif command.lower().startswith('sb'):
            self.sendBroadcastMessage(command, interface)
        elif command.lower().startswith('sd'):
            self.sendDirectMessage(command, interface)
        else:
            print('Unknown keyboard command')

    def printKbdCommands(self):
        print('\n==============================================================================================\nkeyboard commands:')
        print('a  => show APRS participants sent to the APRS-IS')
        print('b  => show bogotrons')
        print('c  => show available commands')
        print('e  => show nodes using encryption')
        print('i  => broadcast ident')
        print('m  => show received messages')
        print('n  => show neighbors')
        print('nt => show nodes table')
        print('q  => quit')
        print('r  => heard since starting')
        # sb 0 this is a test broadcast message to channel 0
        print('sb <ch-index> <message> => send broadcast message')
        # sd !10a37e85 this is a direct message to !10a37e85
        print('sd <to> <message> => send direct message')
        print('==============================================================================================')

    def broadcastIdent(self, interface, createTimer = True):
        ident = 'KD7UBJ Meshtastic APRS/MQTT iGate ({}) v{}. Send "commands" to list services. https://discord.gg/5KUHrjbZ'.format(nodes.gatewayId, version)
        print('\n{} Broadcasting Ident: {}'.format(datetime.datetime.now(), ident))
        interface.sendText(ident, destinationId = '^all', wantAck = False)

        if createTimer:
            self.identTimer = threading.Timer(60 * 60 * 24, self.broadcastIdent, [interface])
            self.identTimer.start()

    def handleRfCommand(self, message, direct):
        # TODO: add ident - about seems to do that...
        if 'about' == message.lower():
            print('Received "about": {}'.format(message))
            return 'KD7UBJ Meshtastic APRS/MQTT iGate ({}) v{}. Send "commands" to list services.'.format(nodes.gatewayId, version)
        elif 'commands' == message.lower():
            print('Received "commands": {}'.format(message))
            return '"about" this iGate.\n"commands" to list possible commands.\n"git" link to this server\'s python source code.\n"ping" to receive pong'
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

    # sb 0 this is a test broadcast message to channel 0
    # sb 1 this is a test broadcast message to channel 1
    def sendBroadcastMessage(self, command, interface):
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
    def sendDirectMessage(self, command, interface):
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

def main():
    global meshaprs
    global nodes
    global neighbors
    global messages
    global aprs
    global bogotron
    global encrypted

    print('Finding Meshtastic device')
    meshaprs = MeshAprs()
    nodes = Nodes(meshaprs.interface)
    neighbors = Neighbors()
    messages = Messages()
    aprs = Aprs()
    encrypted = Encrypted()
    bogotron = Bogotron()

    print('Logging in to APRS-IS')
    aprs.connectAndLoginToAprsIs()

    nodes.getBaseNodeInfo()
    nodes.display()
    meshaprs.printKbdCommands()

    # loop on receive until quit by the user
    meshaprs.startReceive()

    meshaprs.shutdown()
    aprs.shutdown()

    print('Exiting...')

if __name__=='__main__':
    main()
