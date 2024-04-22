#! /usr/bin/python3

from pubsub import pub
import meshtastic
import meshtastic.serial_interface
import time
import datetime
import sys
from socket import *
import traceback 
import select


interface = None
spin = True
messageTable = {}
nodeTable = {}
encryptedTable = []
aprsTable = []
gatewayId = 'N/A'
sock = None
serverHost = 'northwest.aprs2.net'
serverPort = 14578
callSign = 'your_callsign'
callPass = 'your_callsign_pass_code'
version = '0.0.3'
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
        # skip encrypted packets as they cannot be decoded (easily)
        if 'encrypted' in packet:
            print('\nSkipping encrypted packet from {} to {} on channel {}'.format(packet['fromId'], packet['toId'], packet['channel']))
            insertIntoEncryptedTable(packet['rxTime'], packet['fromId'], packet['toId'], packet['channel'])
            print(packet)
            return

        # print from / to line
        print('\n{}: {}: {} => {} on channel {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
            packet['decoded']['portnum'],
            packet['fromId'] if packet['fromId'] != None else 'N/A',
            packet['toId'],
            packet['channel'] if 'channel' in packet else 'N/A'
            )
        )

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
            print('{}: NEIGHBORINFO_APP: rxSnr: {}, hopLimit: {}, rxRssi: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['rxSnr'],
                packet['hopLimit'],
                packet['rxRssi']
                )
            )

        elif packet['decoded']['portnum'] == 'RANGE_TEST_APP':
            print('{}: RANGE_TEST_APP: payload: {}, rxSnr: {}, rxRssi: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet['rxTime'])),
                packet['decoded']['payload'].decode('ascii'),
                dictValueOrDefault('rxSnr', packet),
                dictValueOrDefault('rxRssi', packet)
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
    global aprsISConected
    global callSign

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
                if False == connectAndLoginToAprsIs():
                    print('ERROR: could not log into APRS-IS server: {} port {}'.format(serverHost, serverPort))
                    time.sleep(3)
                    continue

            try:
                sock.send((aprsPacket + '\n').encode())
                print(aprsPacket)
                insertIntoAprsTable(packet['rxTime'], aprsPacket)
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

def insertIntoNodeTable(id, longName, shortName, hwModel):
    global nodeTable
    nodeTable[id] = { 'longName': longName, 'shortName': shortName, 'hwModel': hwModel }

def insertIntoEncryptedTable(rxTime, _from, to, channel):
    global encryptedTable
    encryptedTable.append([rxTime, _from, to, channel])

def insertIntoAprsTable(rxTime, aprsPacket):
    global aprsTable
    aprsTable.append([rxTime, aprsPacket])

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

def displayMessages():
    global messageTable

    print('\n===============================================\n{} messages received:'.format(len(messageTable)))

    try:
        for key in messageTable:
            print("rxTime: {}, fromId: {}, toId: {}, channel: {}, rxSnr: {}, rxRssi: {}, hopLimit: {}, text: {}".format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(key)),
                messageTable[key]['fromId'],
                messageTable[key]['toId'],
                messageTable[key]['channel'],
                messageTable[key]['rxSnr'],
                messageTable[key]['rxRssi'],
                messageTable[key]['hopLimit'],
                messageTable[key]['text']
                )
            )
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('===============================================')

def displayEncrypted():
    global encryptedTable

    print('\n===============================================\n{} encrypted items:'.format(len(encryptedTable)))

    try:
        for message in encryptedTable:
            print('{}: From: {}, To: {}, Channel: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(message[0])),
                message[1],
                message[2],
                message[3]
                )
            )
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('===============================================')

def displayAprs():
    global aprsTable

    print('\n===============================================\n{} APRS packets sent:'.format(len(aprsTable)))

    try:
        for packet in aprsTable:
            print('{}: {}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(packet[0])),
                packet[1]
                )
            )
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

    print('===============================================')

def displayNodes():
    global interface
    global nodeTable

    try:
        nodes = interface.nodes.values()
        print('\n===============================================\n{} nodes seen:'.format(len(nodes)))

        # for node in (sorted(interface.nodes.values(), key = lambda d: d['lastHeard'], reverse = True)):
        for node in nodes:
            print("ID: {} ({}), NAME: {} ({}), MAC: {}, HWMODEL: {}, ROLE: {}, LAT: {}, LON: {}, ALT: {}, TIME: {}, LAST: {}".format(
                node['user']['id'],
                node['num'],
                node['user']['longName'],
                node['user']['shortName'],
                node['user']['macaddr'],
                node['user']['hwModel'],
                node['user']['role'] if 'role' in node['user'] else 'N/A',
                node['position']['latitude'] if 'position' in node and 'latitude' in node['position'] else 'N/A',
                node['position']['longitude'] if 'position' in node and 'longitude' in node['position'] else 'N/A',
                node['position']['altitude'] if 'position' in node and 'altitude' in node['position'] else 'N/A',
                node['position']['time'] if 'position' in node else 'N/A',
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node['lastHeard'])) if 'position' in node else 'N/A'
                )
            )
            insertIntoNodeTable(node['user']['id'], node['user']['longName'], node['user']['shortName'], node['user']['hwModel'])
        print('===============================================')
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        traceback.print_exc()

def broadcastIdent():
    global interface
    global version
    global gatewayId

    ident = 'KD7UBJ Meshtastic APRS/MQTT iGate ({}) v{}. Send "commands" to list services.'.format(gatewayId, version)
    print('\n{} Broadcasting Ident: {}'.format(datetime.datetime.now(), ident))
    interface.sendText(ident, destinationId = '^all', wantAck = False)

# sb 0 this is a test broadcast message to channel 0
# sb 1 this is a test broadcast message to channel 1
def sendBroadcastMessage(command):
    global interface

    print('\n===============================================\nsend broadcast message:')

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

    print('===============================================')

# sd !10a37e85 this is a direct message to !10a37e85
def sendDirectMessage(command):
    global interface

    print('\n===============================================\nsend direct message:')

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

    print('===============================================')

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
        print('\n===============================================\nbroadcast ident:')
        broadcastIdent()
        print('===============================================')
    elif command.lower().startswith('m'):
        displayMessages()
    elif command.lower().startswith('n'):
        displayNodes()
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
    print('\n===============================================\nkeyboard commands:')
    print('a => show APRS data sent to the APRS-IS')
    print('c => show available commands')
    print('e => show nodes using encryption')
    print('i => broadcast ident')
    print('m => show received messages')
    print('n => show nodes table')
    print('q => quit')
    print('sb <ch-index> <message> => send broadcast message')
    # sb 0 this is a test broadcast message to channel 0
    print('sd <to> <message> => send direct message')
    # sd !10a37e85 this is a direct message to !10a37e85
    print('===============================================')

def main():
    global interface
    global spin
    global sock

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

    broadcastIdent()

    spinCount = 0
    while (spin == True):
        if spinCount >= 20 * 60 * 4:
            spinCount = 0
            broadcastIdent()
        else:
            spinCount += 1

        workSleep(.5)

    interface.close()
    if sock != None:
        sock.shutdown(0)
        sock.close()

    print('Exiting...')

if __name__=='__main__':
    main()
